"""
Тесты upgrade_plan / schedule_downgrade / cancel_downgrade (ТЗ §6.4, §12.1).

pro rata чувствителен к точному моменту now() внутри upgrade_plan,
поэтому в тестах на конкретные суммы мы мокаем timezone.now() —
иначе между SetUp и вызовом функции проходят микросекунды и
целочисленное деление дней даёт «не то» число.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import Account
from billing.exceptions import InsufficientFunds, PlanChangeError
from billing.models import BillingTransaction, Plan, Subscription
from billing.services.plan_change import (
    cancel_downgrade,
    schedule_downgrade,
    upgrade_plan,
)
from organizations.models import Organization


User = get_user_model()
VALID_INNS = [
    "7707083893", "7736050003", "7702070139",
    "7740000076", "7728168971", "5024002119",
]


def _make_account_with_subscription(
    name: str, plan_code: str = "free", balance: Decimal = Decimal("0"),
    period_start=None, period_end=None,
):
    user = User.objects.create_user(username=f"u-{name}", password="x")
    account = Account.objects.create(name=name, owner=user, balance=balance)
    user.profile.account = account
    user.profile.save()

    plan = Plan.objects.get(code=plan_code)
    now = timezone.now()
    sub, _ = Subscription.objects.update_or_create(
        account=account,
        defaults={
            "plan": plan,
            "started_at": period_start or now,
            "current_period_start": period_start or now,
            "current_period_end": period_end or (now + timedelta(days=30)),
        },
    )
    account.refresh_from_db()
    return account, user, sub


class UpgradePlanTest(TestCase):
    def test_upgrade_free_to_start_at_period_start_full_price(self):
        """Апгрейд в первый день периода → списание почти полной цены (30/30 дней)."""
        frozen_now = datetime(2026, 2, 1, 10, 0, tzinfo=timezone.get_current_timezone())
        account, _, _ = _make_account_with_subscription(
            "up1", "free", balance=Decimal("2000"),
            period_start=frozen_now,
            period_end=frozen_now + timedelta(days=30),
        )
        with patch("billing.services.plan_change.timezone") as tz_mock:
            tz_mock.now.return_value = frozen_now
            result = upgrade_plan(account, "start")

        # 30 дней осталось → полная цена Старт (1490)
        # pro rata = (1490 - 0) * 30 / 30 = 1490
        self.assertEqual(result["charged"], Decimal("1490.00"))
        self.assertEqual(result["new_plan"], "start")

        account.refresh_from_db()
        self.assertEqual(account.balance, Decimal("510.00"))
        self.assertEqual(account.subscription.plan.code, "start")

        tx = BillingTransaction.objects.get(account=account)
        self.assertEqual(tx.kind, BillingTransaction.Kind.UPGRADE)
        self.assertEqual(tx.amount, Decimal("1490.00"))

    def test_upgrade_with_half_period_passed(self):
        """Апгрейд в середине периода → pro rata ≈ половина разницы цен."""
        frozen_now = datetime(2026, 2, 15, 10, 0, tzinfo=timezone.get_current_timezone())
        # Период: 30 дней, уже прошло 15, осталось 15
        account, _, _ = _make_account_with_subscription(
            "up2", "start", balance=Decimal("3000"),
            period_start=frozen_now - timedelta(days=15),
            period_end=frozen_now + timedelta(days=15),
        )
        with patch("billing.services.plan_change.timezone") as tz_mock:
            tz_mock.now.return_value = frozen_now
            result = upgrade_plan(account, "business")

        # Разница: 4490 - 1490 = 3000. days_left=15, total=30
        # pro rata = 3000 * 15 / 30 = 1500
        self.assertEqual(result["charged"], Decimal("1500.00"))

        account.refresh_from_db()
        self.assertEqual(account.balance, Decimal("1500.00"))
        self.assertEqual(account.subscription.plan.code, "business")

    def test_upgrade_insufficient_funds(self):
        """Недостаток баланса → InsufficientFunds, подписка не меняется."""
        account, _, _ = _make_account_with_subscription("up3", "free", balance=Decimal("0"))
        with self.assertRaises(InsufficientFunds) as cm:
            upgrade_plan(account, "start")
        self.assertIn("требуется", str(cm.exception).lower())

        account.refresh_from_db()
        self.assertEqual(account.subscription.plan.code, "free")  # не сменился
        self.assertEqual(account.balance, Decimal("0"))
        self.assertFalse(BillingTransaction.objects.filter(account=account).exists())

    def test_upgrade_same_or_cheaper_raises(self):
        """Попытка апгрейда на тот же или более дешёвый план — PlanChangeError."""
        account, _, _ = _make_account_with_subscription("up4", "start", balance=Decimal("5000"))
        with self.assertRaises(PlanChangeError):
            upgrade_plan(account, "free")
        with self.assertRaises(PlanChangeError):
            upgrade_plan(account, "start")

    def test_upgrade_resets_scheduled_downgrade(self):
        """При апгрейде отложенный даунгрейд сбрасывается."""
        account, _, sub = _make_account_with_subscription("up5", "start", balance=Decimal("5000"))
        sub.scheduled_plan = Plan.objects.get(code="free")
        sub.save()

        upgrade_plan(account, "business")

        sub.refresh_from_db()
        self.assertIsNone(sub.scheduled_plan_id)


class ScheduleDowngradeTest(TestCase):
    def test_schedule_business_to_start_without_warnings(self):
        """Даунгрейд без превышения лимитов — warnings пустой."""
        account, _, sub = _make_account_with_subscription("d1", "business")

        result = schedule_downgrade(account, "start")
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["effective_at"], sub.current_period_end)

        sub.refresh_from_db()
        self.assertEqual(sub.scheduled_plan.code, "start")

    def test_schedule_with_org_limit_warning(self):
        """
        Business (лимит 10) → Start (лимит 3). У аккаунта 5 своих орг —
        warning, но операция проходит (grandfather).
        """
        account, user, _ = _make_account_with_subscription("d2", "business")
        for inn in VALID_INNS[:5]:
            Organization.objects.create(
                full_name=f"Own-{inn}", short_name=f"O-{inn}",
                inn=inn, is_own_company=True,
                created_by=user, account=account,
            )

        result = schedule_downgrade(account, "start")
        self.assertEqual(len(result["warnings"]), 1)
        self.assertIn("5", result["warnings"][0])
        self.assertIn("3", result["warnings"][0])

        # Операция всё равно применилась
        account.subscription.refresh_from_db()
        self.assertEqual(account.subscription.scheduled_plan.code, "start")

    def test_schedule_with_user_limit_warning(self):
        """Business → Free (user_limit=2) при 4 пользователях — warning."""
        account, user, _ = _make_account_with_subscription("d3", "business")
        for i in range(3):
            extra = User.objects.create_user(username=f"d3-extra-{i}", password="x")
            extra.profile.account = account
            extra.profile.save()

        result = schedule_downgrade(account, "free")
        self.assertTrue(any("пользователей" in w for w in result["warnings"]))

    def test_schedule_upgrade_raises(self):
        """Попытка schedule_downgrade на более дорогой план — PlanChangeError."""
        account, _, _ = _make_account_with_subscription("d4", "start")
        with self.assertRaises(PlanChangeError):
            schedule_downgrade(account, "business")


class CancelDowngradeTest(TestCase):
    def test_cancel_existing_downgrade(self):
        account, _, sub = _make_account_with_subscription("c1", "business")
        schedule_downgrade(account, "start")
        result = cancel_downgrade(account)
        self.assertTrue(result["cancelled"])
        sub.refresh_from_db()
        self.assertIsNone(sub.scheduled_plan_id)

    def test_cancel_when_no_downgrade_is_noop(self):
        account, _, _ = _make_account_with_subscription("c2", "free")
        result = cancel_downgrade(account)
        self.assertFalse(result["cancelled"])
