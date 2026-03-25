import logging
from decimal import Decimal

from django.db import transaction

from billing.constants import (
    DAILY_RATE_ORG,
    DAILY_RATE_USER,
    DAILY_RATE_VEHICLE,
)
from billing.models import BillingTransaction

logger = logging.getLogger("security")

# Порог для логирования подозрительно глубокого ухода в минус
_DEEP_NEGATIVE_THRESHOLD = Decimal("-300.00")


def deposit(account, amount: Decimal, description: str, metadata: dict = None) -> BillingTransaction:
    """
    Пополняет баланс аккаунта.
    Атомарная операция: select_for_update гарантирует корректный баланс
    при параллельных запросах.
    """
    from accounts.models import Account

    with transaction.atomic():
        acc = Account.objects.select_for_update().get(pk=account.pk)
        acc.balance += amount
        acc.save(update_fields=["balance", "updated_at"])

        tx = BillingTransaction.objects.create(
            account=acc,
            kind=BillingTransaction.Kind.DEPOSIT,
            amount=amount,
            balance_after=acc.balance,
            description=description,
            metadata=metadata or {},
        )

    logger.info(
        "billing.deposit account_id=%s amount=%s balance_after=%s",
        acc.pk,
        amount,
        acc.balance,
    )
    return tx


def withdraw(account, amount: Decimal, description: str, metadata: dict = None) -> BillingTransaction:
    """
    Списывает средства с баланса аккаунта.
    Не блокирует операцию — баланс может уйти в минус (до credit_limit).
    """
    from accounts.models import Account

    with transaction.atomic():
        acc = Account.objects.select_for_update().get(pk=account.pk)
        acc.balance -= amount
        acc.save(update_fields=["balance", "updated_at"])

        tx = BillingTransaction.objects.create(
            account=acc,
            kind=BillingTransaction.Kind.CHARGE,
            amount=amount,
            balance_after=acc.balance,
            description=description,
            metadata=metadata or {},
        )

    if acc.balance <= _DEEP_NEGATIVE_THRESHOLD:
        logger.warning(
            "billing.deep_negative account_id=%s balance=%s credit_limit=%s",
            acc.pk,
            acc.balance,
            acc.credit_limit,
        )

    return tx


def can_create_entity(account) -> bool:
    """
    Проверяет, может ли аккаунт создавать новые сущности.
    Блокировка наступает при balance <= credit_limit.
    Аккаунты с is_billing_exempt всегда могут создавать сущности.
    """
    if account.is_billing_exempt:
        return True
    return account.balance > account.credit_limit


def get_daily_cost(account) -> tuple[Decimal, dict]:
    """
    Считает стоимость владения ресурсами за сутки.
    Возвращает (total_cost, breakdown) где breakdown — детализация по типам.

    Оптимизация: три COUNT-запроса вместо загрузки объектов.
    """
    from organizations.models import Organization
    from vehicles.models import Vehicle

    orgs_count = Organization.objects.filter(
        account=account,
        is_own_company=True,
    ).count()

    vehicles_count = Vehicle.objects.filter(
        account=account,
        owner__is_own_company=True,
    ).count()

    users_count = account.profiles.count()

    billable_orgs = max(0, orgs_count - account.free_orgs)
    billable_vehicles = max(0, vehicles_count - account.free_vehicles)
    billable_users = max(0, users_count - account.free_users)

    cost_orgs = billable_orgs * DAILY_RATE_ORG
    cost_vehicles = billable_vehicles * DAILY_RATE_VEHICLE
    cost_users = billable_users * DAILY_RATE_USER
    total = cost_orgs + cost_vehicles + cost_users

    breakdown = {
        "orgs": {"count": orgs_count, "billable": billable_orgs, "cost": float(cost_orgs)},
        "vehicles": {"count": vehicles_count, "billable": billable_vehicles, "cost": float(cost_vehicles)},
        "users": {"count": users_count, "billable": billable_users, "cost": float(cost_users)},
    }

    return total, breakdown
