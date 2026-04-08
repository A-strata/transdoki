from datetime import date

from django.db import transaction
from django.db.models import Max

from trips.models import Trip

from .models import Act, Invoice, InvoiceLine


def _build_route(trip):
    points = list(trip.points.all())
    if not points:
        return "—"
    cities = []
    for p in points:
        city = (p.address or "").split(",")[0].strip()
        if city and (not cities or cities[-1] != city):
            cities.append(city)
    return " → ".join(cities) if cities else "—"


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
    last = (
        Invoice.objects.filter(account=account, number__startswith=prefix)
        .aggregate(m=Max("number"))["m"]
    )
    seq = (int(last.split("-")[-1]) + 1) if last else 1
    return f"{prefix}{seq:04d}"


def next_act_number(account):
    year = date.today().year
    prefix = f"АКТ-{year}-"
    last = (
        Act.objects.filter(account=account, number__startswith=prefix)
        .aggregate(m=Max("number"))["m"]
    )
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
        .select_related("client")
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
            invoice__status__in=[Invoice.Status.DRAFT, Invoice.Status.SENT, Invoice.Status.PAID],
        ).exists():
            already_invoiced.append(t)
    if already_invoiced:
        nums = ", ".join(str(t.num_of_trip) for t in already_invoiced)
        raise ValueError(f"Рейсы уже включены в действующий счёт: {nums}")

    lines = []
    for trip in trips:
        route = _build_route(trip)
        unit_price = trip.client_total or trip.client_cost
        if not unit_price:
            raise ValueError(f"У рейса №{trip.num_of_trip} не указана стоимость.")
        line = InvoiceLine(
            trip=trip,
            kind=InvoiceLine.Kind.SERVICE,
            description=f"Перевозка {route}, {trip.date_of_trip:%d.%m.%Y}",
            unit_price=unit_price,
            discount_pct=0,
            vat_rate=InvoiceLine.VatRate.ZERO,
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
def create_invoice_from_trips(account, trip_ids, user, invoice_date=None,
                              lines_data=None):
    """
    Создаёт Invoice + InvoiceLine из рейсов.

    lines_data — опциональный список dict с пользовательскими правками строк:
        [{"trip_id": int, "description": str, "unit_price": Decimal,
          "discount_pct": Decimal, "vat_rate": int}, ...]
    Если не передан — строки формируются автоматически.
    """
    data = prepare_invoice_data(account, trip_ids)

    invoice = Invoice.objects.create(
        account=account,
        created_by=user,
        number=next_invoice_number(account),
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
                discount_pct=ld.get("discount_pct", 0),
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
    if invoice.status != Invoice.Status.DRAFT:
        raise ValueError("Скидку можно применить только к черновику.")

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
                f"Услуги по перевозке грузов ({route}, "
                f"{trip.date_of_trip:%d.%m.%Y})"
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
