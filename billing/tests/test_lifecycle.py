"""
Тесты process_past_due_accounts (ТЗ §6.6, §12.1) +
проверка, что past_due_since не переписывается при повторных неудачных
charge_monthly (замечание из прошлого раунда).
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import Account
from billing.models import BillingPeriod, Plan, Subscription
from billing.services.charging import charge_monthly
from billing.services.lifecycle import (
    PAST_DUE_GRACE_DAYS,
    process_past_due_accounts,
)


User = get_user_model()


def _make_account_sub(name: str, plan_code: str = "start", balance: Decimal = Decimal("0")):
    user = User.objects.create_user(username=f"lc-{name}", password="x")
    account = Account.objects.create(name=name, owner=user, balance=balance)
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
    account.refresh_from_db()
    return account, sub


class PastDueTransitionTest(TestCase):
    def test_past_due_under_grace_stays_past_due(self):
        """past_due_since=вчера → не suspended (grace не истёк)."""
        account, sub = _make_account_sub("young")
        sub.status = Subscription.Status.PAST_DUE
        sub.past_due_since = timezone.now() - timedelta(days=1)
        sub.save()

        report = process_past_due_accounts()
        self.assertEqual(report["suspended"], 0)

        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.PAST_DUE)

    def test_past_due_beyond_grace_becomes_suspended(self):
        """past_due_since > 14 дней → suspended."""
        account, sub = _make_account_sub("old")
        sub.status = Subscription.Status.PAST_DUE
        sub.past_due_since = timezone.now() - timedelta(days=PAST_DUE_GRACE_DAYS + 1)
        sub.save()

        report = process_past_due_accounts()
        self.assertEqual(report["suspended"], 1)

        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.SUSPENDED)

    def test_active_subscription_not_touched(self):
        """status=active не трогается, даже если past_due_since случайно задан."""
        account, sub = _make_account_sub("active")
        sub.past_due_since = timezone.now() - timedelta(days=30)  # старый, но status=active
        sub.save()

        report = process_past_due_accounts()
        self.assertEqual(report["suspended"], 0)

        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)


class PastDueSinceStabilityTest(TestCase):
    """
    Критичный инвариант: при повторном неудачном charge_monthly
    past_due_since не переписывается — это база для 14-дневного grace
    (иначе клиент никогда бы не достиг suspended).
    """

    def test_repeated_past_due_preserves_past_due_since(self):
        user = User.objects.create_user(username="stab-u", password="x")
        account = Account.objects.create(name="stab", owner=user, balance=Decimal("0"))
        user.profile.account = account
        user.profile.save()

        plan = Plan.objects.get(code="start")
        T0 = timezone.now().replace(microsecond=0)  # «начало»
        # Первый период: закрыт, сдвигать будем в тесте
        sub, _ = Subscription.objects.update_or_create(
            account=account,
            defaults={
                "plan": plan,
                "started_at": T0 - timedelta(days=60),
                "current_period_start": T0 - timedelta(days=31),
                "current_period_end": T0 - timedelta(days=1),
            },
        )

        # Первый charge_monthly: переводит в past_due с past_due_since ≈ T0
        with patch("billing.services.charging.timezone") as tz_mock, \
             patch("billing.services.usage.timezone") as tz_mock2:
            tz_mock.now.return_value = T0
            tz_mock2.now.return_value = T0
            charge_monthly()

        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.PAST_DUE)
        first_past_due_since = sub.past_due_since
        self.assertIsNotNone(first_past_due_since)

        # Симулируем: баланс всё ещё 0, прошёл ещё месяц, период снова закрыт.
        # charge_monthly на первом запуске уже продвинул period вперёд на 1 месяц.
        # Чтобы его повторно обработать, сдвигаем period_end в прошлое.
        sub.current_period_end = T0 + timedelta(days=1)  # в «будущем T1 = T0+30д» — уже прошло
        sub.save()

        T1 = T0 + timedelta(days=35)  # прошло 35 дней с первого past_due
        with patch("billing.services.charging.timezone") as tz_mock, \
             patch("billing.services.usage.timezone") as tz_mock2:
            tz_mock.now.return_value = T1
            tz_mock2.now.return_value = T1
            charge_monthly()

        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.PAST_DUE)
        # past_due_since не сдвинулся
        self.assertEqual(sub.past_due_since, first_past_due_since)

        # BillingPeriod должно быть 2 (оба периода — invoiced)
        self.assertEqual(BillingPeriod.objects.filter(account=account).count(), 2)
        self.assertTrue(
            BillingPeriod.objects.filter(account=account, status="invoiced").count() == 2
        )
