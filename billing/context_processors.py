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

    daily_cost = account.cached_daily_cost or Decimal("0.00")

    return {
        "billing_account": account,
        "billing_is_free": daily_cost == 0 and account.balance == 0,
        "billing_warn_threshold": daily_cost * 3,
        "has_contracts_module": billing_services.account_has_module(
            account, "contracts", request=request
        ),
    }
