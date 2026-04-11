from datetime import date
from decimal import Decimal

from django.db import models, transaction
from django.db.models import Max
from django.http import FileResponse

from contracts.services import _org_context, amount_to_words
from organizations.models import Organization
from trips.models import Trip
from trips.services import BaseDocxGenerator

from .models import Act, Invoice, InvoiceLine, Payment


def _build_description(trip):
    from trips.models import TripPoint

    points = list(trip.points.order_by("sequence").all())

    loads = [p for p in points if p.point_type == TripPoint.Type.LOAD]
    unloads = [p for p in points if p.point_type == TripPoint.Type.UNLOAD]

    first_load_addr = loads[0].address if loads else "—"
    last_unload_addr = unloads[-1].address if unloads else "—"

    first_load_date = loads[0].planned_date if loads else None
    last_unload_date = unloads[-1].planned_date if unloads else None

    parts = [
        f"Перевозка груза по маршруту: {first_load_addr} — {last_unload_addr}",
    ]

    date_parts = []
    if first_load_date:
        date_parts.append(f"дата погрузки {first_load_date:%d.%m.%Y}")
    if last_unload_date:
        date_parts.append(f"дата выгрузки {last_unload_date:%d.%m.%Y}")
    if date_parts:
        parts.append("; ".join(date_parts))

    vehicle_parts = []
    if trip.truck:
        vehicle_parts.append(f"а/м {trip.truck.grn}")
    if trip.trailer:
        vehicle_parts.append(f"прицеп {trip.trailer.grn}")
    if vehicle_parts:
        parts.append(", ".join(vehicle_parts))

    if trip.driver:
        parts.append(f"водитель {trip.driver}")

    return ", ".join(parts) + "."


def _pluralize_trips(n):
    if 11 <= n % 100 <= 19:
        return f"{n} рейсов"
    r = n % 10
    if r == 1:
        return f"{n} рейс"
    if 2 <= r <= 4:
        return f"{n} рейса"
    return f"{n} рейсов"


def next_invoice_number(account):
    year = date.today().year
    prefix = f"СЧ-{year}-"
    last = Invoice.objects.filter(account=account, number__startswith=prefix).aggregate(
        m=Max("number")
    )["m"]
    seq = (int(last.split("-")[-1]) + 1) if last else 1
    return f"{prefix}{seq:04d}"


def next_act_number(account):
    year = date.today().year
    prefix = f"АКТ-{year}-"
    last = Act.objects.filter(account=account, number__startswith=prefix).aggregate(
        m=Max("number")
    )["m"]
    seq = (int(last.split("-")[-1]) + 1) if last else 1
    return f"{prefix}{seq:04d}"


def prepare_invoice_data(account, trip_ids):
    """
    Валидирует рейсы и возвращает предзаполненные данные для формы создания счёта.
    Ничего не записывает в БД.

    Возвращает dict:
        customer: Organization
        trips: list[Trip]
        lines: list[dict]  — предзаполненные строки
        date: date
    Бросает ValueError при проблемах с данными.
    """
    trips = list(
        Trip.objects.for_account(account)
        .filter(pk__in=trip_ids)
        .prefetch_related("points")
        .select_related("client", "truck", "trailer", "driver")
    )

    if not trips:
        raise ValueError("Рейсы не найдены.")

    customers = {t.client_id for t in trips}
    if len(customers) > 1:
        raise ValueError("Все рейсы должны принадлежать одному заказчику.")

    already_invoiced = []
    for t in trips:
        if InvoiceLine.objects.filter(
            trip=t,
            invoice__status__in=[
                Invoice.Status.DRAFT,
                Invoice.Status.SENT,
                Invoice.Status.PAID,
            ],
        ).exists():
            already_invoiced.append(t)
    if already_invoiced:
        nums = ", ".join(str(t.num_of_trip) for t in already_invoiced)
        raise ValueError(f"Рейсы уже включены в действующий счёт: {nums}")

    lines = []
    for trip in trips:
        unit_price = trip.client_total if trip.client_total is not None else trip.client_cost
        if unit_price is None:
            unit_price = Decimal("0")

        line = InvoiceLine(
            trip=trip,
            kind=InvoiceLine.Kind.SERVICE,
            description=_build_description(trip),
            quantity=Decimal("1"),
            unit=InvoiceLine.UnitOfMeasure.SERVICE,
            unit_price=unit_price,
            discount_pct=0,
            vat_rate=trip.client_vat_rate,
        )
        line.compute()
        lines.append(line)

    return {
        "customer": trips[0].client,
        "trips": trips,
        "lines": lines,
        "date": date.today(),
    }


@transaction.atomic
def create_invoice_from_trips(
    account, trip_ids, user, invoice_date=None, lines_data=None, invoice_number=None
):
    """
    Создаёт Invoice + InvoiceLine из рейсов.

    invoice_number — пользовательский номер; если None — генерируется автоматически.
    lines_data — опциональный список dict с пользовательскими правками строк:
        [{"trip_id": int, "description": str, "unit_price": Decimal,
          "discount_amount": Decimal, "vat_rate": int}, ...]
    Если не передан — строки формируются автоматически.
    """
    data = prepare_invoice_data(account, trip_ids)

    invoice = Invoice.objects.create(
        account=account,
        created_by=user,
        number=invoice_number or next_invoice_number(account),
        date=invoice_date or data["date"],
        customer=data["customer"],
        status=Invoice.Status.DRAFT,
    )

    if lines_data:
        trip_map = {t.pk: t for t in data["trips"]}
        for ld in lines_data:
            trip = trip_map.get(ld.get("trip_id"))
            line = InvoiceLine(
                invoice=invoice,
                trip=trip,
                kind=InvoiceLine.Kind.SERVICE,
                description=ld["description"],
                unit_price=ld["unit_price"],
                quantity=ld.get("quantity", Decimal("1")),
                unit=ld.get("unit", InvoiceLine.UnitOfMeasure.SERVICE),
                discount_amount=ld.get("discount_amount", 0),
                vat_rate=ld.get("vat_rate", InvoiceLine.VatRate.ZERO),
            )
            line.compute()
            line.save()
    else:
        for line in data["lines"]:
            line.invoice = invoice
            line.save()

    return invoice


def apply_discount_to_invoice(invoice, discount_pct, user):
    lines = list(invoice.lines.filter(kind=InvoiceLine.Kind.SERVICE))
    for line in lines:
        line.discount_pct = discount_pct
        line.compute(last_edited="pct")

    InvoiceLine.objects.bulk_update(
        lines,
        ["discount_pct", "discount_amount", "amount_net", "vat_amount", "amount_total"],
    )

    invoice.updated_by = user
    invoice.save(update_fields=["updated_by", "updated_at"])


@transaction.atomic
def cancel_invoice(invoice, user):
    if invoice.status == Invoice.Status.PAID:
        raise ValueError("Нельзя аннулировать оплаченный счёт.")

    invoice.lines.all().delete()
    invoice.status = Invoice.Status.CANCELLED
    invoice.updated_by = user
    invoice.save(update_fields=["status", "updated_by", "updated_at"])


def create_payment(organization, date, amount, payment_method, direction, created_by, description=""):
    """
    Регистрирует платёж по контрагенту.

    direction — обязательный: INCOMING (поступление) или OUTGOING (списание/возврат).
    Платёж привязан к контрагенту, не к конкретному счёту или акту.
    Разнесение по актам (PaymentAllocation) — следующий этап.
    """
    if amount <= 0:
        raise ValueError("Сумма платежа должна быть положительной.")

    return Payment.objects.create(
        account=organization.account,
        created_by=created_by,
        organization=organization,
        date=date,
        amount=amount,
        payment_method=payment_method,
        direction=direction,
        description=description,
    )


def delete_payment(payment):
    """Удаляет платёж."""
    payment.delete()


def get_counterparty_balances(account, date_from=None, date_to=None):
    """
    Сальдо по контрагентам: начислено (по подписанным актам), оплачено (платежи), долг.

    Учитываются все платежи по контрагенту — поступления со знаком плюс,
    возвраты (списания) со знаком минус.

    Период фильтрует по Act.date (дата акта) и Payment.date (дата платежа).

    Возвращает queryset Organization с аннотациями: invoiced, paid, balance.
    """
    from django.db.models import Q, Sum, Value
    from django.db.models.functions import Coalesce

    from .models import PaymentDirection

    act_filter = Q(
        invoices__act__account=account,
        invoices__act__status=Act.Status.SIGNED,
    )
    incoming_filter = Q(
        payments__account=account,
        payments__direction=PaymentDirection.INCOMING,
    )
    outgoing_filter = Q(
        payments__account=account,
        payments__direction=PaymentDirection.OUTGOING,
    )

    if date_from:
        act_filter &= Q(invoices__act__date__gte=date_from)
        incoming_filter &= Q(payments__date__gte=date_from)
        outgoing_filter &= Q(payments__date__gte=date_from)
    if date_to:
        act_filter &= Q(invoices__act__date__lte=date_to)
        incoming_filter &= Q(payments__date__lte=date_to)
        outgoing_filter &= Q(payments__date__lte=date_to)

    any_payment_filter = Q(payments__account=account)
    if date_from:
        any_payment_filter &= Q(payments__date__gte=date_from)
    if date_to:
        any_payment_filter &= Q(payments__date__lte=date_to)

    zero = Value(Decimal("0"))

    return (
        Organization.objects.for_account(account)
        .filter(act_filter | any_payment_filter)
        .annotate(
            invoiced=Coalesce(
                Sum("invoices__act__amount_total", filter=act_filter),
                zero,
            ),
            _incoming=Coalesce(
                Sum("payments__amount", filter=incoming_filter),
                zero,
            ),
            _outgoing=Coalesce(
                Sum("payments__amount", filter=outgoing_filter),
                zero,
            ),
        )
        .annotate(paid=models.F("_incoming") - models.F("_outgoing"))
        .annotate(balance=models.F("invoiced") - models.F("paid"))
        .order_by("-balance", "short_name")
    )


def _fmt_money(value):
    """Форматирует Decimal как '1 234,56' для DOCX-шаблона."""
    if value is None:
        return "—"
    value = Decimal(str(value))
    int_part = int(abs(value))
    kopecks = int(round((abs(value) - int_part) * 100))
    formatted = f"{int_part:,}".replace(",", "\u00a0")
    result = f"{formatted},{kopecks:02d}"
    if value < 0:
        result = "-" + result
    return result


class InvoiceGenerator(BaseDocxGenerator):
    """Генератор печатной формы счёта на оплату (DOCX)."""

    template_candidates = ("templates/docs/invoice_template.docx",)

    @classmethod
    def build_context(cls, invoice) -> dict:
        own_company = Organization.objects.filter(
            account=invoice.account,
            is_own_company=True,
        ).first()
        customer = invoice.customer
        lines = list(invoice.lines.select_related("trip").all())

        ctx = {}
        ctx.update(_org_context(own_company, "own_company"))
        ctx.update(_org_context(customer, "contractor"))

        ctx["invoice_number"] = invoice.number
        ctx["invoice_date"] = invoice.date.strftime("%d.%m.%Y") if invoice.date else "—"

        fmt_lines = []
        for line in lines:
            fmt_lines.append(
                {
                    "description": line.description,
                    "quantity": str(line.quantity).rstrip("0").rstrip("."),
                    "unit": line.get_unit_display(),
                    "price": _fmt_money(line.unit_price),
                    "amount": _fmt_money(line.amount_total),
                }
            )
        ctx["lines"] = fmt_lines

        total_net = invoice.total_net
        total_vat = invoice.total_vat
        total = invoice.total

        ctx["total_net"] = _fmt_money(total_net)
        ctx["total"] = _fmt_money(total)
        ctx["items_count"] = len(fmt_lines)
        ctx["amount_words"] = amount_to_words(total)

        if total_vat > 0:
            vat_rates = {ln.vat_rate for ln in lines if ln.vat_rate > 0}
            if len(vat_rates) == 1:
                ctx["vat_text"] = f"В том числе НДС {vat_rates.pop()}%"
            else:
                ctx["vat_text"] = "В том числе НДС"
            ctx["total_vat"] = _fmt_money(total_vat)
        else:
            ctx["vat_text"] = "Без НДС"
            ctx["total_vat"] = "—"

        return ctx

    @classmethod
    def build_download_name(cls, invoice) -> str:
        date_str = invoice.date.strftime("%d.%m.%Y") if invoice.date else ""
        return f"Счёт {invoice.number} от {date_str}.docx"

    @classmethod
    def generate_response(cls, invoice) -> FileResponse:
        context = cls.build_context(invoice)
        buffer = cls._render_to_buffer(context)
        filename = cls.build_download_name(invoice)
        return FileResponse(
            buffer,
            as_attachment=True,
            filename=filename,
            content_type=(
                "application/vnd.openxmlformats-"
                "officedocument.wordprocessingml.document"
            ),
        )


@transaction.atomic
def create_act_from_invoice(invoice, user):
    if Act.objects.filter(invoice=invoice).exists():
        raise ValueError("К этому счёту уже создан акт.")

    service_lines = list(
        invoice.lines.filter(kind=InvoiceLine.Kind.SERVICE).select_related("trip")
    )

    if len(service_lines) == 1:
        line = service_lines[0]
        trip = line.trip
        if trip:
            route = _build_route(trip)
            description = (
                f"Услуги по перевозке грузов ({route}, {trip.date_of_trip:%d.%m.%Y})"
            )
        else:
            description = line.description
    elif service_lines:
        dates = sorted(
            line.trip.date_of_trip
            for line in service_lines
            if line.trip and line.trip.date_of_trip
        )
        date_from = dates[0] if dates else invoice.date
        date_to = dates[-1] if dates else invoice.date
        count = len(service_lines)
        description = (
            f"Услуги по перевозке грузов за период "
            f"{date_from:%d.%m.%Y}–{date_to:%d.%m.%Y}, "
            f"{_pluralize_trips(count)} согласно счёту №{invoice.number}"
        )
    else:
        description = f"Услуги согласно счёту №{invoice.number}"

    act = Act.objects.create(
        account=invoice.account,
        created_by=user,
        number=next_act_number(invoice.account),
        date=date.today(),
        invoice=invoice,
        description=description,
        amount_net=invoice.total_net,
        vat_amount=invoice.total_vat,
        amount_total=invoice.total,
    )

    return act
