"""
Тесты моделей билинга v2: Plan, Subscription, Module, AccountModule,
BillingPeriod, BillingTransaction.

Проверяют:
- effective_* свойства Subscription (fallback на Plan при отсутствии custom)
- UniqueConstraint на BillingPeriod(account, period_start)
- UniqueConstraint на AccountModule(account, module)
- Наличие всех 4 планов и модуля contracts (создано миграцией 0005).
"""
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import Account
from billing.models import (
    AccountModule,
    BillingPeriod,
    Module,
    Plan,
    Subscription,
)


class SeedDataTest(TestCase):
    """Миграция 0005 создала тарифы и модуль contracts."""

    def test_four_plans_seeded(self):
        codes = set(Plan.objects.values_list("code", flat=True))
        self.assertEqual(codes, {"free", "start", "business", "corporate"})

    def test_free_plan_limits(self):
        free = Plan.objects.get(code="free")
        self.assertEqual(free.monthly_price, Decimal("0.00"))
        self.assertEqual(free.trip_limit, 10)
        self.assertEqual(free.user_limit, 2)
        self.assertEqual(free.organization_limit, 1)
        self.assertIsNone(free.overage_price)

    def test_start_plan_limits(self):
        start = Plan.objects.get(code="start")
        self.assertEqual(start.monthly_price, Decimal("1490.00"))
        self.assertEqual(start.trip_limit, 80)
        self.assertEqual(start.user_limit, 5)
        self.assertEqual(start.organization_limit, 3)
        self.assertEqual(start.overage_price, Decimal("22.00"))

    def test_business_plan_limits(self):
        biz = Plan.objects.get(code="business")
        self.assertEqual(biz.monthly_price, Decimal("4490.00"))
        self.assertEqual(biz.trip_limit, 350)
        self.assertEqual(biz.user_limit, 15)
        self.assertEqual(biz.organization_limit, 10)
        self.assertEqual(biz.overage_price, Decimal("16.00"))

    def test_corporate_plan_is_custom_and_unlimited(self):
        corp = Plan.objects.get(code="corporate")
        self.assertTrue(corp.is_custom)
        # Базовые лимиты Corporate из ТЗ: 1200 рейсов, без лимита на орг/пользователей.
        self.assertEqual(corp.trip_limit, 1200)
        self.assertIsNone(corp.user_limit)
        self.assertIsNone(corp.organization_limit)

    def test_contracts_module_seeded_free(self):
        mod = Module.objects.get(code="contracts")
        self.assertEqual(mod.monthly_price, Decimal("0.00"))
        self.assertTrue(mod.is_active)


class SubscriptionEffectiveTest(TestCase):
    """Подписка без custom_* берёт параметры из плана; с custom_* — переопределяет."""

    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(name="Test Account")
        cls.start_plan = Plan.objects.get(code="start")
        cls.corporate_plan = Plan.objects.get(code="corporate")
        now = timezone.now()
        # Subscription уже создана сигналом/миграцией? Нет — Account сам по себе
        # не создаёт подписку, только миграция 0005 делала seed для существующих.
        cls.subscription = Subscription.objects.create(
            account=cls.account,
            plan=cls.start_plan,
            started_at=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )

    def test_effective_falls_back_to_plan(self):
        sub = self.subscription
        self.assertEqual(sub.effective_monthly_price, Decimal("1490.00"))
        self.assertEqual(sub.effective_trip_limit, 80)
        self.assertEqual(sub.effective_user_limit, 5)
        self.assertEqual(sub.effective_organization_limit, 3)
        self.assertEqual(sub.effective_overage_price, Decimal("22.00"))

    def test_custom_overrides_plan(self):
        sub = self.subscription
        sub.custom_monthly_price = Decimal("2000.00")
        sub.custom_trip_limit = 200
        sub.custom_user_limit = 10
        sub.custom_organization_limit = 7
        sub.custom_overage_price = Decimal("19.50")
        sub.save()
        sub.refresh_from_db()

        self.assertEqual(sub.effective_monthly_price, Decimal("2000.00"))
        self.assertEqual(sub.effective_trip_limit, 200)
        self.assertEqual(sub.effective_user_limit, 10)
        self.assertEqual(sub.effective_organization_limit, 7)
        self.assertEqual(sub.effective_overage_price, Decimal("19.50"))

    def test_custom_zero_is_not_null(self):
        """
        custom_trip_limit=0 — валидный override (никаких рейсов не разрешено),
        должен иметь приоритет над plan.trip_limit.
        """
        sub = self.subscription
        sub.custom_trip_limit = 0
        sub.save()
        sub.refresh_from_db()
        self.assertEqual(sub.effective_trip_limit, 0)

    def test_corporate_custom_unlimited(self):
        """Corporate с trip_limit=None на плане и без custom — effective=None (безлимит)."""
        corp_account = Account.objects.create(name="Corp")
        now = timezone.now()
        sub = Subscription.objects.create(
            account=corp_account,
            plan=self.corporate_plan,
            started_at=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        # Corporate.user_limit=None, organization_limit=None по seed-миграции
        self.assertIsNone(sub.effective_user_limit)
        self.assertIsNone(sub.effective_organization_limit)


class UniqueConstraintTest(TestCase):
    """Проверка UniqueConstraint на BillingPeriod и AccountModule."""

    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(name="Test")
        cls.module = Module.objects.get(code="contracts")

    def test_billing_period_unique_account_start(self):
        from datetime import date

        BillingPeriod.objects.create(
            account=self.account,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 2, 1),
            plan_code="free",
            confirmed_trips=0,
            overage_trips=0,
            subscription_fee=Decimal("0"),
            total=Decimal("0"),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BillingPeriod.objects.create(
                    account=self.account,
                    period_start=date(2026, 1, 1),
                    period_end=date(2026, 2, 1),
                    plan_code="free",
                    confirmed_trips=0,
                    overage_trips=0,
                    subscription_fee=Decimal("0"),
                    total=Decimal("0"),
                )

    def test_account_module_unique_pair(self):
        AccountModule.objects.create(account=self.account, module=self.module)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AccountModule.objects.create(
                    account=self.account, module=self.module
                )

    def test_account_has_one_subscription(self):
        """OneToOneField на account не даёт создать две подписки одному аккаунту."""
        now = timezone.now()
        plan = Plan.objects.get(code="free")
        Subscription.objects.create(
            account=self.account,
            plan=plan,
            started_at=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Subscription.objects.create(
                    account=self.account,
                    plan=plan,
                    started_at=now,
                    current_period_start=now,
                    current_period_end=now + timedelta(days=30),
                )
