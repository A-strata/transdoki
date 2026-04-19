"""
Тесты функций лимитов (billing/services/limits.py):
- get_organization_usage, get_user_usage
- can_create_trip, can_create_organization, can_create_user

Покрывают кейсы §12.1 ТЗ + exempt-безлимит (Free+5 орг по-прежнему разрешает создание).
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import Account, UserProfile
from billing.models import Plan, Subscription
from billing.services import limits as limits_service
from organizations.models import Organization


User = get_user_model()


# Валидные ИНН (прошли контрольную сумму). Используем только те, что прошли
# в trips/tests.py — они публичные и стабильные.
VALID_INNS = [
    "7707083893",
    "7736050003",
    "7702070139",
    "7740000076",
    "7728168971",
    "5024002119",
]


def _make_account_with_subscription(name: str, plan_code: str, exempt: bool = False):
    user = User.objects.create_user(username=f"user-{name}", password="x")
    account = Account.objects.create(name=name, owner=user, is_billing_exempt=exempt)
    user.profile.account = account
    user.profile.save()

    plan = Plan.objects.get(code=plan_code)
    now = timezone.now()
    sub, _ = Subscription.objects.update_or_create(
        account=account,
        defaults={
            "plan": plan,
            "started_at": now,
            "current_period_start": now,
            "current_period_end": now + timedelta(days=30),
        },
    )
    # account.subscription мог закешировать старый Free-объект от сигнала.
    # refresh_from_db очищает кеш related-поля.
    account.refresh_from_db()
    return account, user, sub


def _make_own_org(account, user, inn):
    return Organization.objects.create(
        full_name=f"Own {inn}",
        short_name=f"Own{inn}",
        inn=inn,
        is_own_company=True,
        created_by=user,
        account=account,
    )


def _make_counterparty(account, user, inn):
    """Контрагент (is_own_company=False) — не должен считаться в лимит."""
    return Organization.objects.create(
        full_name=f"Cp {inn}",
        short_name=f"Cp{inn}",
        inn=inn,
        is_own_company=False,
        created_by=user,
        account=account,
    )


class OrganizationLimitTest(TestCase):
    """can_create_organization + get_organization_usage."""

    def test_free_with_zero_own_companies_can_create(self):
        account, _, _ = _make_account_with_subscription("free-0", "free")
        ok, msg = limits_service.can_create_organization(account)
        self.assertTrue(ok, msg)

    def test_free_with_one_own_company_cannot_create(self):
        account, user, _ = _make_account_with_subscription("free-1", "free")
        _make_own_org(account, user, VALID_INNS[0])
        ok, msg = limits_service.can_create_organization(account)
        self.assertFalse(ok)
        self.assertIn("Free", msg)
        self.assertIn("1/1", msg)

    def test_start_with_three_own_companies_cannot_create(self):
        account, user, _ = _make_account_with_subscription("start-3", "start")
        for inn in VALID_INNS[:3]:
            _make_own_org(account, user, inn)
        ok, msg = limits_service.can_create_organization(account)
        self.assertFalse(ok)
        self.assertIn("3/3", msg)

    def test_start_with_two_own_companies_can_create(self):
        account, user, _ = _make_account_with_subscription("start-2", "start")
        for inn in VALID_INNS[:2]:
            _make_own_org(account, user, inn)
        ok, msg = limits_service.can_create_organization(account)
        self.assertTrue(ok, msg)

    def test_counterparties_do_not_count_in_org_limit(self):
        """
        Контрагенты (is_own_company=False) не засчитываются в лимит.
        Free-аккаунт с 5 контрагентами и 0 своих компаний — может создать свою.
        """
        account, user, _ = _make_account_with_subscription("free-cp", "free")
        for inn in VALID_INNS[:5]:
            _make_counterparty(account, user, inn)
        usage = limits_service.get_organization_usage(account)
        self.assertEqual(usage["current"], 0)  # в расчёт входят только is_own_company=True
        ok, msg = limits_service.can_create_organization(account)
        self.assertTrue(ok, msg)

    def test_corporate_unlimited_allows_creation(self):
        """Corporate с organization_limit=None → всегда True."""
        account, user, _ = _make_account_with_subscription("corp", "corporate")
        for inn in VALID_INNS[:3]:
            _make_own_org(account, user, inn)
        ok, _ = limits_service.can_create_organization(account)
        self.assertTrue(ok)

    def test_grandfather_after_downgrade_blocks_new(self):
        """
        На Business 5 организаций → даунгрейд до Start (лимит 3) → не блокирует
        существующие, но can_create возвращает False.
        """
        account, user, sub = _make_account_with_subscription("down", "business")
        for inn in VALID_INNS[:5]:
            _make_own_org(account, user, inn)
        # Сейчас на Business (лимит 10) — 5 орг, создание разрешено
        self.assertTrue(limits_service.can_create_organization(account)[0])
        # Даунгрейд
        sub.plan = Plan.objects.get(code="start")
        sub.save()
        account.refresh_from_db()  # очистить кеш account.subscription
        # Теперь 5 > 3 — создание новых запрещено, существующие не затронуты
        ok, msg = limits_service.can_create_organization(account)
        self.assertFalse(ok)
        self.assertIn("5/3", msg)


class UserLimitTest(TestCase):
    """can_create_user + get_user_usage."""

    def _add_profile(self, account, username: str, is_active: bool = True):
        user = User.objects.create_user(username=username, password="x", is_active=is_active)
        user.profile.account = account
        user.profile.save()
        return user

    def test_free_with_two_users_cannot_create(self):
        account, _, _ = _make_account_with_subscription("f-2u", "free")
        self._add_profile(account, "f-2u-extra1")
        # Owner уже есть через _make_account_with_subscription (1 профиль).
        # 1 + 1 = 2, достигнут лимит Free
        usage = limits_service.get_user_usage(account)
        self.assertEqual(usage["current"], 2)
        self.assertEqual(usage["limit"], 2)
        ok, msg = limits_service.can_create_user(account)
        self.assertFalse(ok)
        self.assertIn("2/2", msg)

    def test_business_with_ten_users_can_create(self):
        account, _, _ = _make_account_with_subscription("biz-10", "business")
        # owner уже 1 → добавим 9 ещё
        for i in range(9):
            self._add_profile(account, f"biz-10-extra-{i}")
        ok, _ = limits_service.can_create_user(account)
        self.assertTrue(ok)

    def test_inactive_user_does_not_count(self):
        """Деактивированный user.is_active=False не засчитывается в лимит."""
        account, _, _ = _make_account_with_subscription("inactive", "free")
        # owner активен → 1. Добавим неактивного → не попадает в счёт.
        self._add_profile(account, "inactive-extra", is_active=False)
        usage = limits_service.get_user_usage(account)
        self.assertEqual(usage["current"], 1)  # только owner
        ok, _ = limits_service.can_create_user(account)
        self.assertTrue(ok)


class BillingExemptTest(TestCase):
    """is_billing_exempt=True игнорирует все лимиты."""

    def test_exempt_account_bypasses_all_limits(self):
        """Free с 5 организациями и is_billing_exempt=True — всё можно."""
        account, user, _ = _make_account_with_subscription("exempt", "free", exempt=True)
        # 5 организаций на Free-лимите 1 — должно быть можно
        for inn in VALID_INNS[:5]:
            _make_own_org(account, user, inn)

        ok, _ = limits_service.can_create_organization(account)
        self.assertTrue(ok)

        # can_create_user тоже True, независимо от числа пользователей
        ok, _ = limits_service.can_create_user(account)
        self.assertTrue(ok)

        # can_create_trip — тоже True
        ok, _ = limits_service.can_create_trip(account)
        self.assertTrue(ok)

    def test_exempt_even_when_subscription_past_due(self):
        """
        Exempt обходит даже past_due. Это важно для внутренних/служебных
        аккаунтов: если на них почему-то выставлен past_due — они не должны
        блокироваться.
        """
        account, _, sub = _make_account_with_subscription("exempt-pd", "free", exempt=True)
        sub.status = Subscription.Status.PAST_DUE
        sub.save()
        self.assertTrue(limits_service.can_create_trip(account)[0])
        self.assertTrue(limits_service.can_create_organization(account)[0])
        self.assertTrue(limits_service.can_create_user(account)[0])


class TripCreationStatusTest(TestCase):
    """can_create_trip учитывает статус подписки, но не считает рейсы."""

    def test_active_subscription_allows(self):
        account, _, _ = _make_account_with_subscription("active", "free")
        ok, _ = limits_service.can_create_trip(account)
        self.assertTrue(ok)

    def test_past_due_blocks(self):
        account, _, sub = _make_account_with_subscription("pd", "free")
        sub.status = Subscription.Status.PAST_DUE
        sub.save()
        ok, msg = limits_service.can_create_trip(account)
        self.assertFalse(ok)
        self.assertIn("Задолженность", msg)

    def test_suspended_blocks(self):
        account, _, sub = _make_account_with_subscription("susp", "free")
        sub.status = Subscription.Status.SUSPENDED
        sub.save()
        ok, msg = limits_service.can_create_trip(account)
        self.assertFalse(ok)

    def test_cancelled_blocks(self):
        account, _, sub = _make_account_with_subscription("canc", "free")
        sub.status = Subscription.Status.CANCELLED
        sub.save()
        ok, msg = limits_service.can_create_trip(account)
        self.assertFalse(ok)
