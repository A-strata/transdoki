"""
Смена тарифного плана (ТЗ §6.4).

upgrade_plan — немедленный апгрейд с pro rata: разница цен за оставшиеся
дни списывается с баланса сразу, подписка переводится на новый план.

schedule_downgrade — отложенный даунгрейд: scheduled_plan выставляется,
применяется в charge_monthly после закрытия текущего периода. Если новые
лимиты меньше текущего использования — вернуть warnings для UI, но
операцию не блокировать (grandfather-режим, см. §3.4 ТЗ).

cancel_downgrade — сброс scheduled_plan.

Pro rata считается целыми днями (ТЗ, Приложение A, п.6): days_left / total_days.
Это стандарт Stripe и большинства SaaS-биллингов; копеечные погрешности
от секунды не принципиальны, а детерминированность по дате упрощает UX.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from billing.exceptions import InsufficientFunds, PlanChangeError
from billing.models import BillingTransaction, Plan, Subscription
from billing.services.limits import get_organization_usage, get_user_usage


logger = logging.getLogger("billing")


def _get_plan_or_raise(plan_code: str) -> Plan:
    try:
        return Plan.objects.get(code=plan_code, is_active=True)
    except Plan.DoesNotExist as exc:
        raise PlanChangeError(f"Тариф {plan_code!r} не найден или неактивен") from exc


def _pro_rata(amount: Decimal, days_left: int, total_days: int) -> Decimal:
    """
    Вычисляет pro rata: сумма × оставшиеся дни / всего дней.
    Округление до копеек вниз — клиенту не начисляем больше, чем положено.

    При total_days == 0 возвращает 0 — граничный случай (period_end == period_start),
    реально не встречается, но подстраховка.
    """
    if total_days <= 0:
        return Decimal("0")
    if days_left <= 0:
        return Decimal("0")
    raw = amount * Decimal(days_left) / Decimal(total_days)
    return raw.quantize(Decimal("0.01"))


def upgrade_plan(account, new_plan_code: str) -> dict:
    """
    Немедленный апгрейд с pro rata-списанием разницы цен.

    Args:
        account: аккаунт с активной подпиской
        new_plan_code: код более дорогого плана

    Returns:
        {'new_plan': str, 'charged': Decimal} — код нового плана и списанная сумма

    Raises:
        PlanChangeError — план не найден, или не является апгрейдом
        InsufficientFunds — на балансе не хватает pro rata-разницы
    """
    subscription = account.subscription
    current_plan = subscription.plan
    new_plan = _get_plan_or_raise(new_plan_code)

    if new_plan.monthly_price <= subscription.effective_monthly_price:
        raise PlanChangeError(
            f"Апгрейд невозможен: {new_plan.name} ({new_plan.monthly_price}₽) не дороже "
            f"текущего {current_plan.name} ({subscription.effective_monthly_price}₽). "
            f"Используйте schedule_downgrade для перехода на более дешёвый план."
        )

    now = timezone.now()
    total_days = (subscription.current_period_end - subscription.current_period_start).days
    days_left = (subscription.current_period_end - now).days
    # Целочисленное деление — стандарт Stripe. См. ТЗ, Приложение A, п.6.

    price_diff = new_plan.monthly_price - subscription.effective_monthly_price
    pro_rata = _pro_rata(price_diff, days_left, total_days)

    if pro_rata > 0 and account.balance < pro_rata:
        raise InsufficientFunds(
            f"Для перехода на тариф {new_plan.name} требуется {pro_rata} ₽, "
            f"на балансе: {account.balance} ₽. Пополните баланс."
        )

    with transaction.atomic():
        if pro_rata > 0:
            _charge_balance(
                account,
                pro_rata,
                BillingTransaction.Kind.UPGRADE,
                description=(
                    f"Апгрейд {current_plan.name} → {new_plan.name} "
                    f"(pro rata за {days_left} из {total_days} дней)"
                ),
            )
        subscription.plan = new_plan
        # При апгрейде отменяем отложенный даунгрейд (если был)
        subscription.scheduled_plan = None
        subscription.save(update_fields=["plan", "scheduled_plan", "updated_at"])

    logger.info(
        "plan_change.upgrade account_id=%s %s→%s charged=%s",
        account.pk, current_plan.code, new_plan.code, pro_rata,
    )
    return {"new_plan": new_plan.code, "charged": pro_rata}


def schedule_downgrade(account, new_plan_code: str) -> dict:
    """
    Отложенный даунгрейд: применится в ближайшем charge_monthly.

    При превышении лимитов новым планом — возвращает warnings для UI,
    но операция не блокируется (grandfather-режим ТЗ §3.4).

    Args:
        account: аккаунт с активной подпиской
        new_plan_code: код более дешёвого плана

    Returns:
        {
            'effective_at': datetime,  # когда применится
            'warnings':     list[str], # предупреждения о превышении лимитов
        }

    Raises:
        PlanChangeError — план не найден / не является даунгрейдом
    """
    subscription = account.subscription
    current_plan = subscription.plan
    new_plan = _get_plan_or_raise(new_plan_code)

    if new_plan.monthly_price > subscription.effective_monthly_price:
        raise PlanChangeError(
            f"Даунгрейд невозможен: {new_plan.name} ({new_plan.monthly_price}₽) дороже "
            f"текущего {current_plan.name} ({subscription.effective_monthly_price}₽). "
            f"Используйте upgrade_plan для перехода на более дорогой план."
        )

    warnings: list[str] = []

    org_usage = get_organization_usage(account)
    if (
        new_plan.organization_limit is not None
        and org_usage["current"] > new_plan.organization_limit
    ):
        warnings.append(
            f"У вас {org_usage['current']} собственных организаций, "
            f"на тарифе «{new_plan.name}» разрешено {new_plan.organization_limit}. "
            f"Существующие останутся, но добавить новые будет нельзя."
        )

    user_usage = get_user_usage(account)
    if (
        new_plan.user_limit is not None
        and user_usage["current"] > new_plan.user_limit
    ):
        warnings.append(
            f"У вас {user_usage['current']} пользователей, "
            f"на тарифе «{new_plan.name}» разрешено {new_plan.user_limit}. "
            f"Существующие останутся, но добавить новых будет нельзя."
        )

    subscription.scheduled_plan = new_plan
    subscription.save(update_fields=["scheduled_plan", "updated_at"])

    logger.info(
        "plan_change.schedule_downgrade account_id=%s %s→%s effective=%s warnings=%d",
        account.pk, current_plan.code, new_plan.code,
        subscription.current_period_end, len(warnings),
    )
    return {
        "effective_at": subscription.current_period_end,
        "warnings": warnings,
    }


def cancel_downgrade(account) -> dict:
    """Сбрасывает отложенный даунгрейд. Идемпотентно."""
    subscription = account.subscription
    if subscription.scheduled_plan_id is None:
        return {"cancelled": False, "reason": "Нет отложенного даунгрейда"}

    prev_scheduled = subscription.scheduled_plan.code
    subscription.scheduled_plan = None
    subscription.save(update_fields=["scheduled_plan", "updated_at"])

    logger.info(
        "plan_change.cancel_downgrade account_id=%s cancelled=%s",
        account.pk, prev_scheduled,
    )
    return {"cancelled": True, "prev_scheduled_plan": prev_scheduled}


def _charge_balance(
    account,
    amount: Decimal,
    kind: str,
    description: str = "",
) -> BillingTransaction:
    """
    Списывает amount с баланса и создаёт BillingTransaction.

    Используется внутри transaction.atomic() из plan_change/modules —
    собственной транзакции не открывает.

    ВАЖНО: дублирует логику из charging._charge_balance. Когда накопится
    третий case, вынести в shared helper (например, в balance.py). Пока
    дублирование проще, чем преждевременная абстракция.
    """
    from accounts.models import Account

    acc = Account.objects.select_for_update().get(pk=account.pk)
    acc.balance -= amount
    acc.save(update_fields=["balance", "updated_at"])

    tx = BillingTransaction.objects.create(
        account=acc,
        kind=kind,
        amount=amount,
        balance_after=acc.balance,
        description=description,
    )
    # Обновляем переданный экземпляр, чтобы вызывающий видел свежий balance
    account.balance = acc.balance
    return tx
