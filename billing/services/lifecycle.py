"""
Жизненный цикл подписок: past_due → suspended (ТЗ §6.6).

Grace-период — 14 дней (ТЗ Приложение A, п.1). Если подписка висит в
past_due дольше — переводим в suspended. В suspended клиент теряет
возможность создавать новые сущности (can_create_trip/organization/user
вернут False по _subscription_status_ok).

past_due_since — момент ПЕРВОГО перехода в past_due, не обновляется при
повторных неудачных charge_monthly. Это зафиксировано в charging.py
и является базой для расчёта grace.
"""
import logging
from datetime import timedelta

from django.utils import timezone

from billing.models import Subscription


logger = logging.getLogger("billing")

# ТЗ Приложение A, п.1
PAST_DUE_GRACE_DAYS = 14


def process_past_due_accounts() -> dict:
    """
    Переводит просроченные past_due-подписки в suspended.

    Запускается ежедневно (ТЗ §10). Аккаунты с past_due_since > 14 дней
    назад получают status=suspended и теряют доступ к созданию сущностей.

    Returns:
        {'processed': int, 'suspended': int}
    """
    cutoff = timezone.now() - timedelta(days=PAST_DUE_GRACE_DAYS)

    qs = Subscription.objects.select_related("account").filter(
        status=Subscription.Status.PAST_DUE,
        past_due_since__isnull=False,
        past_due_since__lt=cutoff,
    )

    suspended_count = 0
    for subscription in qs:
        subscription.status = Subscription.Status.SUSPENDED
        subscription.save(update_fields=["status", "updated_at"])
        logger.warning(
            "lifecycle.suspend account_id=%s past_due_since=%s",
            subscription.account_id, subscription.past_due_since,
        )
        # TODO (итерация 6): send_billing_notification(subscription.account,
        #     "suspended", {"past_due_since": subscription.past_due_since})
        suspended_count += 1

    report = {"processed": qs.count(), "suspended": suspended_count}
    logger.info(
        "lifecycle.process_past_due done: processed=%d suspended=%d "
        "(grace=%d days)",
        report["processed"], report["suspended"], PAST_DUE_GRACE_DAYS,
    )
    return report
