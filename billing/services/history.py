"""
Единая история биллинговых событий для UI.

HistoryEvent — адаптер над BillingTransaction и BillingPeriod. Один формат
для рендеринга в шаблоне, независимо от источника. Direction («credit /
debit / nominal») задаёт цвет и знак суммы.

build_history(account, filters) — объединённый отсортированный список
событий с применёнными фильтрами. Объединение выполняется в Python, это
оправдано пока записей мало (у активного клиента ~50 транзакций / 12
периодов в год). Если упрёмся — перейти на SQL UNION.
"""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from django.db.models import Q

from billing.models import BillingPeriod, BillingTransaction


Direction = Literal["credit", "debit", "nominal"]

# Классификация kind'ов транзакций. Должна совпадать с разметкой в history.html.
_CREDIT_KINDS = {
    BillingTransaction.Kind.DEPOSIT,
    BillingTransaction.Kind.REFUND,
}
_DEBIT_KINDS = {
    BillingTransaction.Kind.CHARGE,
    BillingTransaction.Kind.SUBSCRIPTION,
    BillingTransaction.Kind.OVERAGE,
    BillingTransaction.Kind.MODULE,
    BillingTransaction.Kind.UPGRADE,
}
# adjustment считаем nominal — в UI показываем без знака/цвета «операция».

_KIND_LABELS = {
    BillingTransaction.Kind.DEPOSIT: "Пополнение",
    BillingTransaction.Kind.REFUND: "Возврат",
    BillingTransaction.Kind.CHARGE: "Списание",
    BillingTransaction.Kind.SUBSCRIPTION: "Подписка",
    BillingTransaction.Kind.OVERAGE: "Overage",
    BillingTransaction.Kind.MODULE: "Модуль",
    BillingTransaction.Kind.UPGRADE: "Апгрейд тарифа",
    BillingTransaction.Kind.ADJUSTMENT: "Корректировка",
}


@dataclass
class HistoryEvent:
    """Единое представление события для шаблона истории."""
    date: datetime
    kind: str            # код события: "deposit"/"upgrade"/.../"period"
    label: str           # человекочитаемое имя: "Пополнение" / "Расчётный период"
    direction: Direction
    amount: Decimal
    balance_after: Decimal | None   # None для period-событий
    description: str
    status: str | None = None       # для period: "paid"/"invoiced"/"written_off"
    status_label: str | None = None


def _transaction_to_event(tx: BillingTransaction) -> HistoryEvent:
    if tx.kind in _CREDIT_KINDS:
        direction: Direction = "credit"
    elif tx.kind in _DEBIT_KINDS:
        direction = "debit"
    else:
        direction = "nominal"

    return HistoryEvent(
        date=tx.created_at,
        kind=tx.kind,
        label=_KIND_LABELS.get(tx.kind, "Операция"),
        direction=direction,
        amount=tx.amount,
        balance_after=tx.balance_after,
        description=tx.description,
    )


def _period_to_event(bp: BillingPeriod, plan_names: dict[str, str]) -> HistoryEvent:
    plan_name = plan_names.get(bp.plan_code, bp.plan_code)
    desc_parts = [
        f"{bp.period_start:%d.%m.%Y}—{bp.period_end:%d.%m.%Y}",
        plan_name,
        f"{bp.confirmed_trips} рейсов",
    ]
    if bp.overage_trips:
        desc_parts.append(f"overage +{bp.overage_trips}")
    if bp.modules_fee and bp.modules_fee > 0:
        desc_parts.append(f"модули {bp.modules_fee:.0f} ₽")

    return HistoryEvent(
        date=_aware(bp.created_at),
        kind="period",
        label="Расчётный период",
        direction="nominal",
        amount=bp.total,
        balance_after=None,
        description=" • ".join(desc_parts),
        status=bp.status,
        status_label=bp.get_status_display(),
    )


def _aware(value):
    """BillingPeriod.created_at уже timezone-aware, но на всякий случай нормализуем."""
    return value


def build_history(
    account,
    *,
    event_type: str = "all",
    date_from: date | None = None,
    date_to: date | None = None,
    period_status: str | None = None,
) -> list[HistoryEvent]:
    """
    Собрать единую историю событий аккаунта с применёнными фильтрами.

    event_type:
      'all'                — всё
      'credit'             — пополнения + возвраты
      'debit'              — все списания (подписка, overage, модули, апгрейды, legacy charge)
      'period'             — только расчётные периоды
      '<kind>'             — конкретный kind транзакции (deposit/upgrade/subscription/...)

    date_from / date_to — границы по дате события (включительно).
    period_status — фильтр статуса для 'period' (paid/invoiced/written_off).

    Возвращает список, отсортированный по date desc.
    """
    from billing.models import Plan

    plan_names = {p.code: p.name for p in Plan.objects.all()}

    # ── Транзакции ───────────────────────────────────────────────────
    tx_qs = BillingTransaction.objects.filter(account=account)
    if date_from:
        tx_qs = tx_qs.filter(created_at__date__gte=date_from)
    if date_to:
        tx_qs = tx_qs.filter(created_at__date__lte=date_to)

    if event_type == "period":
        tx_qs = tx_qs.none()
    elif event_type == "credit":
        tx_qs = tx_qs.filter(kind__in=_CREDIT_KINDS)
    elif event_type == "debit":
        tx_qs = tx_qs.filter(kind__in=_DEBIT_KINDS)
    elif event_type != "all":
        # Конкретный kind
        tx_qs = tx_qs.filter(kind=event_type)

    # ── Расчётные периоды ────────────────────────────────────────────
    # Черновые (draft) не показываем — это промежуточное состояние.
    bp_qs = BillingPeriod.objects.filter(account=account).exclude(
        status=BillingPeriod.Status.DRAFT
    )
    if date_from:
        bp_qs = bp_qs.filter(created_at__date__gte=date_from)
    if date_to:
        bp_qs = bp_qs.filter(created_at__date__lte=date_to)

    # Если фильтр не показывает периоды — скрываем
    period_filters_active = event_type in ("all", "period")
    if not period_filters_active:
        bp_qs = bp_qs.none()
    elif period_status:
        bp_qs = bp_qs.filter(status=period_status)

    # ── Объединение + сортировка ─────────────────────────────────────
    events: list[HistoryEvent] = [
        _transaction_to_event(tx) for tx in tx_qs
    ] + [
        _period_to_event(bp, plan_names) for bp in bp_qs
    ]
    events.sort(key=lambda e: e.date, reverse=True)
    return events
