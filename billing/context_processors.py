from billing import services as billing_services
from billing.services.balance_state import get_balance_state
from billing.services.limits import can_create_organization
from transdoki.tenancy import get_request_account


def billing_account(request):
    """
    Инжектирует базовые данные биллинга в контекст всех шаблонов.
    Один запрос к БД — только если пользователь авторизован.
    """
    if not request.user.is_authenticated:
        return {}

    try:
        account = get_request_account(request)
    except Exception:
        return {}

    subscription = getattr(account, "subscription", None)
    is_free_plan = bool(subscription and subscription.plan_id and subscription.plan.code == "free")

    return {
        "billing_account": account,
        "billing_is_free": is_free_plan,
        "has_contracts_module": billing_services.account_has_module(
            account, "contracts", request=request
        ),
    }


def billing_alert(request):
    """
    Единый source-of-truth для алертов о балансе.

    Три канала оповещения (бейдж в навбаре, inline-алерт в ЛК, глобальный
    баннер) читают один и тот же BalanceState — это гарантирует, что они
    показывают согласованную информацию.
    """
    if not request.user.is_authenticated:
        return {}

    try:
        account = get_request_account(request)
    except Exception:
        return {}

    state = get_balance_state(account)
    return {
        "billing_alert": state,
        "billing_alert_code": state.code,
    }


def org_limits(request):
    """
    Контекст own-лимита для сайдбара и других мест вне list-views.

    Считает текущее число собственных организаций и сверяет с лимитом
    тарифа. Использует can_create_organization — та же функция, что в
    dispatch и list-views, гарантирует единообразное поведение для
    exempt-аккаунтов, отсутствующей подписки и free-tier.

    Инжектируется один раз на запрос; внутри list-views те же поля
    перекрываются локальным контекстом (значения совпадают).
    """
    if not request.user.is_authenticated:
        return {}

    try:
        account = get_request_account(request)
    except Exception:
        return {}

    # Импорт здесь, а не на уровне модуля — чтобы billing не имел жёсткой
    # зависимости от organizations (который может не быть в INSTALLED_APPS
    # на время миграций или отдельных management-команд).
    from organizations.models import Organization

    ok, _ = can_create_organization(account)
    subscription = getattr(account, "subscription", None)
    limit = (
        subscription.effective_organization_limit
        if subscription is not None
        else None
    )
    current = (
        Organization.objects.for_account(account)
        .filter(is_own_company=True)
        .count()
    )
    return {
        "can_create_own_org": ok,
        "org_limit": limit,
        "org_count_current": current,
    }
