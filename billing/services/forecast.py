"""
Прогноз следующего списания для UI.

Выделено из SubscriptionView.get_context_data, чтобы переиспользовать
на странице личного кабинета (accounts:cabinet) без дублирования логики.
Ничего по сути не меняет: формирует те же поля, что раньше собирались в view.

Ключевая схема:
    plan_fee    — effective_monthly_price подписки
    overage_fee — overage по confirmed-рейсам за текущий период
    modules_fee — сумма monthly_price активных AccountModule
    total       — plan_fee + overage_fee + modules_fee
    balance_insufficient — True, если баланс меньше total

Функция чистая: читает БД, не пишет. Безопасна к повторному вызову.
"""

from __future__ import annotations

from decimal import Decimal

from .usage import get_trip_usage


def estimate_period_forecast(account, subscription) -> dict:
    """
    Возвращает прогноз следующего списания по подписке аккаунта.

    Args:
        account: Account-tenant
        subscription: активная Subscription аккаунта (не None)

    Returns:
        {
            "plan_fee":             Decimal,
            "overage_trips":        int,
            "overage_fee":          Decimal,
            "modules_fee":          Decimal,
            "total":                Decimal,
            "period_end":           datetime,
            "balance_insufficient": bool,
        }

    Если subscription=None — возвращает структуру с нулями. Это защита на
    случай нарушенного инварианта (у Account должна быть подписка всегда).
    """
    if subscription is None:
        return {
            "plan_fee": Decimal("0"),
            "overage_trips": 0,
            "overage_fee": Decimal("0"),
            "modules_fee": Decimal("0"),
            "total": Decimal("0"),
            "period_end": None,
            "balance_insufficient": False,
        }

    trip_usage = get_trip_usage(
        account,
        subscription.current_period_start,
        subscription.current_period_end,
    )

    if trip_usage["limit"] is not None and trip_usage["confirmed"] > trip_usage["limit"]:
        overage_trips = trip_usage["confirmed"] - trip_usage["limit"]
        overage_price = subscription.effective_overage_price or Decimal("0")
        overage_fee = overage_trips * overage_price
    else:
        overage_trips = 0
        overage_fee = Decimal("0")

    modules_fee = sum(
        (
            am.module.monthly_price
            for am in account.account_modules.filter(is_active=True).select_related("module")
        ),
        Decimal("0"),
    )

    plan_fee = subscription.effective_monthly_price
    total = plan_fee + overage_fee + modules_fee

    return {
        "plan_fee": plan_fee,
        "overage_trips": overage_trips,
        "overage_fee": overage_fee,
        "modules_fee": modules_fee,
        "total": total,
        "period_end": subscription.current_period_end,
        "balance_insufficient": total > 0 and account.balance < total,
    }
