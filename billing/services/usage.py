"""
Подсчёт использования рейсов для биллинга и UI.

Бизнес-правило (ТЗ §3.3):
- confirmed — рейс прожил > 24 часов с момента created_at, не удалён ИЛИ
  удалён позже чем через 24ч после создания. Такие рейсы попадают в расчёт
  подписки/overage.
- pending — рейс создан в последние 24 часа и не удалён. Ещё может быть
  удалён без последствий для биллинга.
- total — confirmed + pending, отображается в UI как общий счётчик.

Рейс принадлежит календарному месяцу своего created_at (ТЗ §3.3):
фильтр period_start <= created_at < period_end. Удалённые рейсы старше 24ч
от момента создания должны тарифицироваться, поэтому используется
Trip.all_objects — дефолтный Trip.objects скрывает удалённые и ломает
правило. Это архитектурный инвариант, зафиксированный в §4 ТЗ.
"""
from datetime import datetime, timedelta

from django.db.models import Count, F, Q
from django.utils import timezone

from trips.models import Trip


def get_trip_usage(account, period_start: datetime, period_end: datetime) -> dict:
    """
    Возвращает состояние использования рейсов в указанном периоде.

    Args:
        account: tenant-аккаунт
        period_start, period_end: границы периода (наивные или aware —
            используются как есть для фильтра по created_at)

    Returns:
        {
            'confirmed': int,  # рейсы, вошедшие в расчёт (возраст > 24ч)
            'pending':   int,  # рейсы в суточном окне (ещё могут быть удалены)
            'total':     int,  # confirmed + pending (для UI)
            'limit':     int | None,  # effective_trip_limit подписки, None = безлимит
        }

    Важно: используется Trip.all_objects, не Trip.objects. Правило 24ч
    требует видеть удалённые рейсы, чтобы корректно отличить «удалён
    в 24ч окне» (не тарифицируется) от «удалён позже» (тарифицируется).
    """
    now = timezone.now()
    cutoff_24h = now - timedelta(hours=24)

    # Критерий confirmed: возраст > 24ч AND (не удалён ИЛИ удалён позже 24ч
    # от created_at). Выражение deleted_at > created_at + 24h реализует
    # «прожил дольше суточного окна перед удалением».
    delete_after_24h = Q(deleted_at__gt=F("created_at") + timedelta(hours=24))
    not_deleted = Q(deleted_at__isnull=True)

    stats = (
        Trip.all_objects.for_account(account)
        .filter(created_at__gte=period_start, created_at__lt=period_end)
        .aggregate(
            confirmed=Count(
                "id",
                filter=Q(created_at__lt=cutoff_24h) & (not_deleted | delete_after_24h),
            ),
            pending=Count(
                "id",
                filter=Q(created_at__gte=cutoff_24h) & not_deleted,
            ),
        )
    )

    subscription = getattr(account, "subscription", None)
    limit = subscription.effective_trip_limit if subscription else None

    return {
        "confirmed": stats["confirmed"] or 0,
        "pending": stats["pending"] or 0,
        "total": (stats["confirmed"] or 0) + (stats["pending"] or 0),
        "limit": limit,
    }
