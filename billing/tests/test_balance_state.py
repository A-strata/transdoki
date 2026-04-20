"""
Unit-тесты чистой функции get_balance_state.

5 состояний + граничные случаи:
- exempt → ok
- free-tier → ok независимо от баланса
- active: ok / upcoming / urgent по порогам
- past_due → past_due с failed_at и suspended_at
- suspended → suspended
- нет подписки → ok
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import Account
from billing.models import BillingPeriod, Plan, Subscription
from billing.services.balance_state import get_balance_state
from billing.services.lifecycle import PAST_DUE_GRACE_DAYS

User = get_user_model()


def _make_account(name: str, balance: Decimal = Decimal("0"), *, exempt: bool = False):
    user = User.objects.create_user(username=f"bs-{name}", password="x")
    account = Account.objects.create(
        name=name, owner=user, balance=balance, is_billing_exempt=exempt,
    )
    user.profile.account = account
    user.profile.save()
    return account


def _switch_plan(account, plan_code: str):
    """Переключить автосозданную Free-подписку на нужный план."""
    plan = Plan.objects.get(code=plan_code)
    sub = account.subscription
    sub.plan = plan
    now = timezone.now()
    sub.current_period_start = now
    sub.current_period_end = now + timedelta(days=30)
    sub.save()
    return sub


class ExemptTest(TestCase):
    def test_exempt_always_ok(self):
        account = _make_account("exempt", balance=Decimal("-1000"), exempt=True)
        state = get_balance_state(account)
        self.assertEqual(state.code, "ok")
        self.assertEqual(state.balance, Decimal("-1000"))
        self.assertIsNone(state.next_charge_amount)
        self.assertIsNone(state.amount_to_topup)


class FreeTierTest(TestCase):
    def test_free_plan_always_ok_even_with_zero_balance(self):
        account = _make_account("free", balance=Decimal("0"))
        # Сигнал уже назначил Free-подписку при создании аккаунта.
        self.assertEqual(account.subscription.plan.code, Plan.CODE_FREE)
        state = get_balance_state(account)
        self.assertEqual(state.code, "ok")


class ActiveOkTest(TestCase):
    def test_balance_above_2x_price_is_ok(self):
        account = _make_account("rich", balance=Decimal("3000"))
        sub = _switch_plan(account, Plan.CODE_START)
        # balance >= price * 2
        self.assertGreaterEqual(account.balance, sub.effective_monthly_price * 2)
        state = get_balance_state(account)
        self.assertEqual(state.code, "ok")
        self.assertEqual(state.next_charge_amount, sub.effective_monthly_price)
        self.assertEqual(state.next_charge_date, sub.current_period_end)


class ActiveUpcomingTest(TestCase):
    def test_balance_between_1x_and_2x_is_upcoming(self):
        account = _make_account("mid", balance=Decimal("0"))
        sub = _switch_plan(account, Plan.CODE_START)
        price = sub.effective_monthly_price
        # 1x <= balance < 2x
        account.balance = price + Decimal("1")
        account.save()
        state = get_balance_state(account)
        self.assertEqual(state.code, "upcoming")
        self.assertEqual(state.next_charge_amount, price)
        self.assertEqual(state.next_charge_date, sub.current_period_end)
        self.assertIsNone(state.amount_to_topup)


class ActiveUrgentTest(TestCase):
    def test_balance_below_price_is_urgent(self):
        account = _make_account("low", balance=Decimal("0"))
        sub = _switch_plan(account, Plan.CODE_START)
        price = sub.effective_monthly_price
        account.balance = price - Decimal("100")
        account.save()
        state = get_balance_state(account)
        self.assertEqual(state.code, "urgent")
        self.assertEqual(state.next_charge_amount, price)
        self.assertEqual(state.amount_to_topup, Decimal("100"))

    def test_zero_balance_urgent_topup_equals_price(self):
        account = _make_account("zero", balance=Decimal("0"))
        sub = _switch_plan(account, Plan.CODE_START)
        state = get_balance_state(account)
        self.assertEqual(state.code, "urgent")
        self.assertEqual(state.amount_to_topup, sub.effective_monthly_price)

    def test_negative_balance_urgent_topup_clamped_to_price(self):
        """При отрицательном балансе amount_to_topup = price (не price + |balance|)."""
        account = _make_account("neg", balance=Decimal("-50"))
        sub = _switch_plan(account, Plan.CODE_START)
        state = get_balance_state(account)
        self.assertEqual(state.code, "urgent")
        self.assertEqual(state.amount_to_topup, sub.effective_monthly_price)


class PastDueTest(TestCase):
    def test_past_due_with_invoiced_debt(self):
        account = _make_account("pd", balance=Decimal("200"))
        _switch_plan(account, Plan.CODE_START)
        sub = account.subscription
        sub.status = Subscription.Status.PAST_DUE
        sub.past_due_since = timezone.now() - timedelta(days=3)
        sub.save()
        BillingPeriod.objects.create(
            account=account,
            period_start=(timezone.now() - timedelta(days=33)).date(),
            period_end=(timezone.now() - timedelta(days=3)).date(),
            plan_code="start",
            confirmed_trips=0, overage_trips=0,
            subscription_fee=Decimal("1490"),
            total=Decimal("1490"),
            status=BillingPeriod.Status.INVOICED,
        )
        state = get_balance_state(account)
        self.assertEqual(state.code, "past_due")
        self.assertEqual(state.amount_to_topup, Decimal("1290"))  # 1490 - 200
        self.assertEqual(state.failed_at, sub.past_due_since)
        expected_suspend = sub.past_due_since + timedelta(days=PAST_DUE_GRACE_DAYS)
        self.assertEqual(state.suspended_at, expected_suspend)


class SuspendedTest(TestCase):
    def test_suspended_fills_topup_from_invoiced(self):
        account = _make_account("susp", balance=Decimal("0"))
        _switch_plan(account, Plan.CODE_START)
        sub = account.subscription
        sub.status = Subscription.Status.SUSPENDED
        sub.past_due_since = timezone.now() - timedelta(days=20)
        sub.save()
        BillingPeriod.objects.create(
            account=account,
            period_start=(timezone.now() - timedelta(days=50)).date(),
            period_end=(timezone.now() - timedelta(days=20)).date(),
            plan_code="start",
            confirmed_trips=0, overage_trips=0,
            subscription_fee=Decimal("1490"),
            total=Decimal("1490"),
            status=BillingPeriod.Status.INVOICED,
        )
        state = get_balance_state(account)
        self.assertEqual(state.code, "suspended")
        self.assertEqual(state.amount_to_topup, Decimal("1490"))
