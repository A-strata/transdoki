"""
Сигналы билинга.

auto_create_free_subscription: при создании нового Account сразу создаёт
Free-подписку на 1 месяц. Гарантирует, что каждый Account имеет
Subscription — это инвариант, от которого зависят can_create_trip,
get_trip_usage, charge_monthly и т.д. (ТЗ §3.5).
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from accounts.models import Account
from billing.models import Plan, Subscription
from billing.services.charging import _add_months


logger = logging.getLogger("billing")


@receiver(post_save, sender=Account)
def auto_create_free_subscription(sender, instance: Account, created: bool, **kwargs):
    """
    При регистрации нового аккаунта сразу создаёт подписку на план Free.

    Идемпотентно: если подписка уже есть (created=False, или она была
    создана через data-миграцию 0005), ничего не делает.

    Если план Free почему-то отсутствует в БД (например, в тесте до
    применения всех миграций) — тихо пропускаем, чтобы не ломать случаи,
    где Subscription намеренно создаётся руками.
    """
    if not created:
        return

    if hasattr(instance, "subscription") and instance.subscription is not None:
        return

    try:
        free_plan = Plan.objects.get(code="free")
    except Plan.DoesNotExist:
        logger.warning(
            "auto_create_free_subscription: Plan 'free' not found, skipping "
            "for account_id=%s", instance.pk,
        )
        return

    now = timezone.now()
    Subscription.objects.create(
        account=instance,
        plan=free_plan,
        billing_cycle=Subscription.BillingCycle.MONTHLY,
        status=Subscription.Status.ACTIVE,
        started_at=now,
        current_period_start=now,
        current_period_end=_add_months(now, 1),
    )
    logger.info(
        "auto_create_free_subscription: created Free sub for account_id=%s",
        instance.pk,
    )
