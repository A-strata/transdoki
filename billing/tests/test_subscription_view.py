"""
Тесты SubscriptionView (/billing/subscription/) и AJAX-эндпоинтов смены тарифа.

Покрывают:
- GET страницы: статус 200, наличие блоков
- POST upgrade: успех, InsufficientFunds → 402 с required/balance
- POST schedule_downgrade: успех с warnings
- POST cancel_downgrade: успех
- context_processor billing_alert: past_due, suspended, active
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Account
from billing.models import BillingPeriod, Plan, Subscription

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["*"])
class SubscriptionViewGetTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u-sub", password="x")
        self.account = Account.objects.create(
            name="A", owner=self.user, balance=Decimal("0"),
        )
        self.user.profile.account = self.account
        self.user.profile.save()
        # Сигнал уже создал Free-sub
        self.client = Client()
        self.client.force_login(self.user)

    def test_page_renders_with_all_blocks(self):
        r = self.client.get(reverse("billing:subscription"))
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        self.assertIn("plan-change-modal", content)
        self.assertIn("insufficient-funds-modal", content)
        # Редизайн: прогресс-бары лимитов используют класс .lk-progress
        # (общий компонент из lk-tokens.css).
        self.assertIn("lk-progress", content)
        # Текущий Free
        self.assertIn("Free", content)

    def test_corporate_shows_contact_manager(self):
        sub = self.account.subscription
        sub.plan = Plan.objects.get(code="corporate")
        sub.save()
        r = self.client.get(reverse("billing:subscription"))
        content = r.content.decode()
        self.assertIn("mailto:", content)
        self.assertNotIn('data-modal-open="plan-change-modal"', content)

    def test_scheduled_downgrade_shown(self):
        sub = self.account.subscription
        sub.plan = Plan.objects.get(code="business")
        sub.scheduled_plan = Plan.objects.get(code="start")
        sub.save()
        r = self.client.get(reverse("billing:subscription"))
        content = r.content.decode()
        # Плашка с названием запланированного плана
        self.assertIn("Старт", content)


@override_settings(ALLOWED_HOSTS=["*"])
class SubscriptionUpgradeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="up-u", password="x")
        self.account = Account.objects.create(
            name="up", owner=self.user, balance=Decimal("2000"),
        )
        self.user.profile.account = self.account
        self.user.profile.save()
        self.client = Client()
        self.client.force_login(self.user)

    def test_upgrade_success(self):
        r = self.client.post(
            reverse("billing:subscription_upgrade"),
            {"plan_code": "start"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["new_plan"], "start")
        self.account.refresh_from_db()
        self.assertEqual(self.account.subscription.plan.code, "start")

    def test_upgrade_insufficient_funds_returns_402_with_required(self):
        # На Free → Start требуется 1490 ₽, баланс 0
        self.account.balance = Decimal("0")
        self.account.save()

        r = self.client.post(
            reverse("billing:subscription_upgrade"),
            {"plan_code": "start"},
        )
        self.assertEqual(r.status_code, 402)
        body = r.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["plan_code"], "start")
        self.assertIsNotNone(body["required"])
        self.assertEqual(body["balance"], "0.00")
        # Подписка не поменялась
        self.account.refresh_from_db()
        self.assertEqual(self.account.subscription.plan.code, "free")

    def test_upgrade_to_cheaper_plan_rejected(self):
        # Сначала на business
        sub = self.account.subscription
        sub.plan = Plan.objects.get(code="business")
        sub.save()

        r = self.client.post(
            reverse("billing:subscription_upgrade"),
            {"plan_code": "start"},
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["ok"])

    def test_upgrade_missing_plan_code(self):
        r = self.client.post(reverse("billing:subscription_upgrade"), {})
        self.assertEqual(r.status_code, 400)


@override_settings(ALLOWED_HOSTS=["*"])
class SubscriptionScheduleDowngradeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dn-u", password="x")
        self.account = Account.objects.create(
            name="dn", owner=self.user, balance=Decimal("5000"),
        )
        self.user.profile.account = self.account
        self.user.profile.save()
        # Переключаем на business
        sub = self.account.subscription
        sub.plan = Plan.objects.get(code="business")
        sub.save()
        self.client = Client()
        self.client.force_login(self.user)

    def test_schedule_success(self):
        r = self.client.post(
            reverse("billing:subscription_schedule_downgrade"),
            {"plan_code": "start"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["plan_code"], "start")
        self.assertEqual(body["warnings"], [])

    def test_cancel_downgrade(self):
        # Сначала запланируем
        self.client.post(
            reverse("billing:subscription_schedule_downgrade"),
            {"plan_code": "start"},
        )
        # Потом отменим
        r = self.client.post(reverse("billing:subscription_cancel_downgrade"))
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["cancelled"])


@override_settings(ALLOWED_HOSTS=["*"])
class BillingBannerTest(TestCase):
    """context_processor billing_alert: past_due, suspended, active."""

    def setUp(self):
        self.user = User.objects.create_user(username="bn-u", password="x")
        self.account = Account.objects.create(name="bn", owner=self.user)
        self.user.profile.account = self.account
        self.user.profile.save()
        self.client = Client()
        self.client.force_login(self.user)

    def test_active_no_banner(self):
        r = self.client.get(reverse("billing:subscription"))
        self.assertNotIn("billing-alert-bar", r.content.decode())

    def test_past_due_shows_banner_with_debt(self):
        sub = self.account.subscription
        sub.status = Subscription.Status.PAST_DUE
        sub.past_due_since = timezone.now() - timedelta(days=3)
        sub.save()
        # invoiced-период с долгом
        BillingPeriod.objects.create(
            account=self.account,
            period_start=timezone.now().date() - timedelta(days=33),
            period_end=timezone.now().date() - timedelta(days=3),
            plan_code="start",
            confirmed_trips=0, overage_trips=0,
            subscription_fee=Decimal("1490"),
            total=Decimal("1490"),
            status=BillingPeriod.Status.INVOICED,
        )
        r = self.client.get(reverse("billing:subscription"))
        content = r.content.decode()
        self.assertIn("billing-alert-bar", content)
        self.assertIn("1490", content)
        # 14 - 3 = 11 дней осталось
        self.assertIn("11", content)

    def test_suspended_shows_suspended_banner(self):
        sub = self.account.subscription
        sub.status = Subscription.Status.SUSPENDED
        sub.save()
        r = self.client.get(reverse("billing:subscription"))
        content = r.content.decode()
        self.assertIn("billing-alert-bar", content)
        self.assertIn("ограничен", content.lower())

    def test_exempt_no_banner_even_past_due(self):
        self.account.is_billing_exempt = True
        self.account.save()
        sub = self.account.subscription
        sub.status = Subscription.Status.PAST_DUE
        sub.past_due_since = timezone.now() - timedelta(days=10)
        sub.save()
        r = self.client.get(reverse("billing:subscription"))
        self.assertNotIn("billing-alert-bar", r.content.decode())
