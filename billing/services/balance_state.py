"""
Источник истины для алертов о балансе.

Разделяет актуальное состояние биллинга аккаунта на 5 кодов:
ok / upcoming / urgent / past_due / suspended. Каждый код всегда
несёт конкретную сумму и дату — не «пополните баланс», а
«пополните на X ₽, иначе {date} тариф уйдёт в past_due».

Три канала оповещения (бейдж в навбаре, inline-алерт в ЛК,
глобальный баннер) читают один и тот же BalanceState — это
гарантирует, что они согласованы.

Exempt-аккаунты и free-tier — всегда ok.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from django.utils import timezone

from billing.models import BillingPeriod, Plan, Subscription
from billing.services.lifecycle import PAST_DUE_GRACE_DAYS

StateCode = Literal["ok", "upcoming", "urgent", "past_due", "suspended"]


@dataclass(frozen=True)
class BalanceState:
    code: StateCode
    balance: Decimal
    # «Сколько спишется в ближайшее списание» — для upcoming/urgent.
    # Для past_due/suspended не заполняется (факт списания уже в прошлом).
    next_charge_amount: Decimal | None = None
    next_charge_date: datetime | None = None
    # Рекомендованная сумма пополнения. Заполняется для urgent/past_due/suspended.
    amount_to_topup: Decimal | None = None
    # Только для past_due/suspended.
    failed_at: datetime | None = None
    suspended_at: datetime | None = None

    @property
    def days_until_suspended(self) -> int | None:
        """Для past_due — сколько целых дней осталось до автоматического suspend."""
        if self.code != "past_due" or self.suspended_at is None:
            return None
        delta = self.suspended_at - timezone.now()
        return max(0, delta.days)


def _last_invoiced_debt(account) -> Decimal:
    """Сумма долга = total последнего BillingPeriod со статусом INVOICED."""
    last = (
        BillingPeriod.objects.filter(
            account=account, status=BillingPeriod.Status.INVOICED
        )
        .order_by("-period_start")
        .first()
    )
    return last.total if last else Decimal("0")


def get_balance_state(account) -> BalanceState:
    """
    Вычисляет текущее состояние баланса аккаунта для UI-алертов.

    Read-only: не трогает БД на запись. Все дорогие выборки —
    одно обращение к BillingPeriod только для past_due/suspended.
    """
    balance = account.balance

    if account.is_billing_exempt:
        return BalanceState(code="ok", balance=balance)

    subscription = getattr(account, "subscription", None)
    if subscription is None or subscription.plan_id is None:
        return BalanceState(code="ok", balance=balance)

    # Статусы past_due/suspended обрабатываем ДО проверки free-tier:
    # если подписка зависла в past_due/suspended, мы обязаны показать
    # алерт, даже если в этот момент план технически Free (после downgrade).
    if subscription.status == Subscription.Status.PAST_DUE:
        debt = _last_invoiced_debt(account)
        amount_to_topup = max(debt - balance, Decimal("0")) if debt else Decimal("0")
        suspended_at = None
        if subscription.past_due_since is not None:
            suspended_at = subscription.past_due_since + _grace_timedelta()
        return BalanceState(
            code="past_due",
            balance=balance,
            amount_to_topup=amount_to_topup,
            failed_at=subscription.past_due_since,
            suspended_at=suspended_at,
        )

    if subscription.status == Subscription.Status.SUSPENDED:
        debt = _last_invoiced_debt(account)
        amount_to_topup = max(debt - balance, Decimal("0")) if debt else Decimal("0")
        return BalanceState(
            code="suspended",
            balance=balance,
            amount_to_topup=amount_to_topup,
            failed_at=subscription.past_due_since,
        )

    # Free tier в active-статусе — без алертов независимо от баланса.
    if subscription.plan.code == Plan.CODE_FREE:
        return BalanceState(code="ok", balance=balance)

    # active: пороги по effective_monthly_price.
    price = subscription.effective_monthly_price
    next_charge_date = subscription.current_period_end

    if price <= Decimal("0"):
        # Индивидуальный тариф с нулевой ценой — алерты не нужны.
        return BalanceState(code="ok", balance=balance)

    if balance >= price * Decimal("2"):
        return BalanceState(
            code="ok",
            balance=balance,
            next_charge_amount=price,
            next_charge_date=next_charge_date,
        )

    if balance >= price:
        return BalanceState(
            code="upcoming",
            balance=balance,
            next_charge_amount=price,
            next_charge_date=next_charge_date,
        )

    # 0 <= balance < price — urgent. amount_to_topup = price - balance.
    # balance может быть отрицательным (перерасход) — clamp к price.
    shortfall = price - balance if balance >= 0 else price
    return BalanceState(
        code="urgent",
        balance=balance,
        next_charge_amount=price,
        next_charge_date=next_charge_date,
        amount_to_topup=shortfall,
    )


def _grace_timedelta():
    """timedelta для grace-периода past_due → suspended (14 дней)."""
    return timedelta(days=PAST_DUE_GRACE_DAYS)
