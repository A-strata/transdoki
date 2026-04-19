from decimal import Decimal

from billing import services as billing_services
from transdoki.tenancy import get_request_account


def billing_account(request):
    """
    Инжектирует данные биллинга в контекст всех шаблонов.
    Один запрос к БД — только если пользователь авторизован.
    """
    if not request.user.is_authenticated:
        return {}

    try:
        account = get_request_account(request)
    except Exception:
        return {}

    # billing_is_free: True если у аккаунта Free-подписка. После перехода на
    # v2 «бесплатно» означает подписку free (не «нулевой баланс»), независимо
    # от того, пополнял ли аккаунт баланс.
    subscription = getattr(account, "subscription", None)
    is_free_plan = bool(subscription and subscription.plan_id and subscription.plan.code == "free")

    # billing_warn_threshold: порог, ниже которого баланс подсвечивается в навбаре.
    # До реализации месячного биллинга (итерация 3) — ориентируемся на effective
    # цену подписки × 3 (запас на 3 месяца). Для free — 0, варнинг не сработает.
    if subscription and subscription.plan_id:
        warn_threshold = subscription.effective_monthly_price * Decimal("3")
    else:
        warn_threshold = Decimal("0")

    return {
        "billing_account": account,
        "billing_is_free": is_free_plan,
        "billing_warn_threshold": warn_threshold,
        "has_contracts_module": billing_services.account_has_module(
            account, "contracts", request=request
        ),
    }
