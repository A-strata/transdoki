"""
Проверки лимитов тарифа (ТЗ §3.4, §6.2).

Правила:
- Лимит организаций считается только от собственных компаний
  (is_own_company=True). Контрагенты — справочник и не лимитируются.
- Лимит пользователей — активные UserProfile аккаунта (user.is_active=True).
- Лимит рейсов — мягкий, превышение не блокирует создание, но начисляется
  overage в конце месяца. can_create_trip проверяет только статус подписки.
- is_billing_exempt → все лимиты игнорируются, can_create_* возвращает True.

effective_* свойства Subscription уже учитывают custom_* для Corporate:
если custom_X задан — используется он, иначе plan.X.
"""

from billing.models import Subscription


def _get_subscription(account) -> Subscription | None:
    """Безопасное получение подписки; None если OneToOne не установлен."""
    return getattr(account, "subscription", None)


def get_trip_usage_shallow(account) -> dict:
    """
    Упрощённая версия usage-счётчика для can_create_trip — без аггрегата по БД.

    can_create_trip не нуждается в точном числе рейсов (лимит мягкий),
    ему нужен только статус подписки. Поэтому счётчики не считаем.

    Для UI и charge_monthly — использовать billing.services.usage.get_trip_usage.
    """
    subscription = _get_subscription(account)
    return {
        "limit": subscription.effective_trip_limit if subscription else None,
    }


def get_organization_usage(account) -> dict:
    """
    Текущее число собственных организаций (is_own_company=True) vs лимит.

    Сейчас Organization не имеет флага активности/soft-delete — учитываются
    все существующие. Если в будущем добавится архивация, фильтр
    is_active/deleted_at дописать здесь и в can_create_organization.

    Контрагенты (is_own_company=False) в расчёт лимита не входят (ТЗ §3.4).
    """
    subscription = _get_subscription(account)
    limit = subscription.effective_organization_limit if subscription else None
    current = account.organization_set.filter(is_own_company=True).count()
    return {"current": current, "limit": limit}


def get_vehicle_usage(account) -> dict:
    """
    Текущее число ТС аккаунта vs лимит.

    Сейчас лимит ТС в тарифах не задан — всегда возвращается limit=None.
    Когда в Plan появится vehicle_limit (отдельная задача), достаточно
    будет использовать subscription.effective_vehicle_limit по аналогии
    с другими usage-функциями.
    """
    from vehicles.models import Vehicle

    current = Vehicle.objects.for_account(account).count()
    return {"current": current, "limit": None}


def get_user_usage(account) -> dict:
    """
    Текущее число активных пользователей аккаунта vs лимит.

    Активный пользователь — профиль с user.is_active=True. Деактивированные
    пользователи в лимит не засчитываются (не могут логиниться).
    """
    subscription = _get_subscription(account)
    limit = subscription.effective_user_limit if subscription else None
    current = account.profiles.filter(user__is_active=True).count()
    return {"current": current, "limit": limit}


def _subscription_status_ok(account) -> tuple[bool, str]:
    """
    Общая проверка: аккаунт имеет активную подписку, статус не заблокирован.
    Возвращает (True, "") или (False, "понятный текст ошибки").

    is_billing_exempt — всегда True (проверяется в can_create_* до этой функции).
    """
    subscription = _get_subscription(account)
    if not subscription:
        return False, "Нет активной подписки. Обратитесь в поддержку."

    if subscription.status in (Subscription.Status.SUSPENDED, Subscription.Status.CANCELLED):
        return False, (
            f"Подписка в статусе {subscription.get_status_display()}. "
            "Создание новых сущностей невозможно."
        )

    if subscription.status == Subscription.Status.PAST_DUE:
        return False, (
            "Задолженность по оплате подписки. Пополните баланс для "
            "восстановления доступа."
        )

    return True, ""


def can_create_trip(account) -> tuple[bool, str]:
    """
    Проверка перед созданием рейса.

    Лимит рейсов — мягкий: превышение не блокирует, overage начисляется
    в конце месяца. Блокирует только состояние подписки (past_due/suspended).
    """
    if account.is_billing_exempt:
        return True, ""
    return _subscription_status_ok(account)


def can_create_organization(account) -> tuple[bool, str]:
    """
    Проверка перед созданием собственной организации (is_own_company=True).

    Жёсткий лимит: при достижении — запрещено создавать новые, существующие
    не трогаются (grandfather-режим при даунгрейде).

    Для контрагентов (is_own_company=False) эта проверка не применяется —
    они не считаются в лимит. Вызывающий код должен вызывать can_create_organization
    только для создания своих компаний.
    """
    if account.is_billing_exempt:
        return True, ""

    ok, msg = _subscription_status_ok(account)
    if not ok:
        return ok, msg

    usage = get_organization_usage(account)
    if usage["limit"] is None:
        return True, ""
    if usage["current"] >= usage["limit"]:
        plan_name = account.subscription.plan.name
        return False, (
            f"Достигнут лимит организаций на тарифе {plan_name} "
            f"({usage['current']}/{usage['limit']}). "
            "Перейдите на тариф выше или удалите существующую организацию."
        )
    return True, ""


def can_create_user(account) -> tuple[bool, str]:
    """
    Проверка перед созданием пользователя аккаунта.

    Жёсткий лимит; grandfather при даунгрейде.
    """
    if account.is_billing_exempt:
        return True, ""

    ok, msg = _subscription_status_ok(account)
    if not ok:
        return ok, msg

    usage = get_user_usage(account)
    if usage["limit"] is None:
        return True, ""
    if usage["current"] >= usage["limit"]:
        plan_name = account.subscription.plan.name
        return False, (
            f"Достигнут лимит пользователей на тарифе {plan_name} "
            f"({usage['current']}/{usage['limit']}). "
            "Перейдите на тариф выше."
        )
    return True, ""
