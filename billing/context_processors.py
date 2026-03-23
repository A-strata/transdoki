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

    return {
        "billing_account": account,
    }
