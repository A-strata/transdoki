from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from billing import services as billing_services
from billing.models import BillingPeriod, Subscription
from billing.services.lifecycle import PAST_DUE_GRACE_DAYS
from billing.services.limits import can_create_organization
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


def billing_banner(request):
    """
    Контекст для баннера past_due / suspended в base.html.

    Возвращает только при релевантном статусе — в остальных случаях пусто,
    чтобы base.html выводил баннер через `{% if billing_banner %}`.

    Exempt-аккаунты и аккаунты без подписки баннер не видят.
    """
    if not request.user.is_authenticated:
        return {}

    try:
        account = get_request_account(request)
    except Exception:
        return {}

    if account.is_billing_exempt:
        return {}

    subscription = getattr(account, "subscription", None)
    if not subscription:
        return {}

    if subscription.status == Subscription.Status.PAST_DUE and subscription.past_due_since:
        days_passed = (timezone.now() - subscription.past_due_since).days
        days_until_suspended = max(0, PAST_DUE_GRACE_DAYS - days_passed)

        # Последний invoiced-период — сумма задолженности
        last_invoiced = (
            BillingPeriod.objects.filter(
                account=account, status=BillingPeriod.Status.INVOICED
            )
            .order_by("-period_start")
            .first()
        )
        debt_amount = last_invoiced.total if last_invoiced else Decimal("0")

        return {
            "billing_banner": {
                "kind": "past_due",
                "days_until_suspended": days_until_suspended,
                "debt_amount": debt_amount,
                "past_due_since": subscription.past_due_since,
            }
        }

    if subscription.status == Subscription.Status.SUSPENDED:
        return {
            "billing_banner": {
                "kind": "suspended",
            }
        }

    return {}


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
