from decimal import Decimal

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Max, ProtectedError, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import FileResponse
from django.utils.timezone import localdate

from contracts.services import _org_context, amount_to_words
from organizations.models import Organization
from trips.models import Trip, TripPoint
from trips.services import BaseDocxGenerator

from .models import Invoice, InvoiceLine, Payment, PaymentDirection

# ─────────────────────────────────────────────────────────────────────
# Хелперы
# ─────────────────────────────────────────────────────────────────────


def _require_account(user):
    """Извлекает account из user.profile, бросает ValidationError если нет."""
    profile = getattr(user, "profile", None)
    account = getattr(profile, "account", None)
    if account is None:
        raise ValidationError("У пользователя не найден account.")
    return account


def _build_description(trip):
    """Текстовое наименование строки счёта по рейсу."""
    points = list(trip.points.order_by("sequence").all())
    loads = [p for p in points if p.point_type == TripPoint.Type.LOAD]
    unloads = [p for p in points if p.point_type == TripPoint.Type.UNLOAD]

    first_load_addr = loads[0].address if loads else "—"
    last_unload_addr = unloads[-1].address if unloads else "—"

    first_load_date = loads[0].planned_date if loads else None
    last_unload_date = unloads[-1].planned_date if unloads else None

    parts = [f"Перевозка груза по маршруту: {first_load_addr} — {last_unload_addr}"]

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


def _check_trips_availability(trip_ids, account_id, exclude_invoice=None):
    """
    Блокирует и проверяет что рейсы не заняты другим счётом.

    Вызывать только внутри transaction.atomic().
    select_for_update(of=("self",)) — блокирует только InvoiceLine,
    не связанную Invoice-таблицу, чтобы избежать взаимных блокировок
    с update_invoice на ту же шапку.

    list() на qs обязательно — без него select_for_update ленив и
    блокировка не применяется.
    """
    if not trip_ids:
        return

    qs = InvoiceLine.objects.select_for_update(of=("self",)).filter(
        trip_id__in=trip_ids, invoice__account_id=account_id
    )
    if exclude_invoice is not None:
        qs = qs.exclude(invoice=exclude_invoice)

    busy = list(qs.values_list("trip__num_of_trip", flat=True))
    if busy:
        raise ValidationError(
            {
                NON_FIELD_ERRORS: f"Рейсы уже включены в другой счёт: {', '.join(map(str, busy))}",
            }
        )


# ─────────────────────────────────────────────────────────────────────
# Invoice — prepare / create / update
# ─────────────────────────────────────────────────────────────────────


def prepare_invoice_data(user, trip_ids):
    """
    Валидирует рейсы и собирает данные для префилла формы.
    Ничего не пишет в БД.

    Возвращает dict:
        customer: Organization
        lines:    list[dict] — готово и для initial= в формсете,
                  и для передачи в create_invoice(lines_data=...)

    Занятость рейсов здесь не проверяется: она требует atomic-блока
    и проверяется внутри create_invoice.
    """
    account = _require_account(user)

    trips = list(
        Trip.objects.for_account(account)
        .filter(pk__in=trip_ids)
        .prefetch_related("points")
        .select_related("client", "truck", "trailer", "driver")
    )

    if not trips:
        raise ValidationError({NON_FIELD_ERRORS: "Рейсы не найдены."})

    customers = {t.client_id for t in trips}
    if len(customers) > 1:
        raise ValidationError(
            {
                NON_FIELD_ERRORS: "Все рейсы должны принадлежать одному заказчику.",
            }
        )

    lines = []
    for trip in trips:
        unit_price = (
            trip.client_total if trip.client_total is not None else trip.client_cost
        )
        if unit_price is None:
            raise ValidationError(
                {
                    NON_FIELD_ERRORS: f"У рейса №{trip.num_of_trip} не указана стоимость для клиента.",
                }
            )

        lines.append(
            {
                "trip": trip,
                "kind": InvoiceLine.Kind.SERVICE,
                "description": _build_description(trip),
                "quantity": Decimal("1"),
                "unit": InvoiceLine.UnitOfMeasure.SERVICE,
                "unit_price": unit_price,
                "discount_amount": Decimal("0"),
                "vat_rate": trip.client_vat_rate,
            }
        )

    return {
        "customer": trips[0].client,
        "lines": lines,
    }


def create_invoice(
    *,
    user,
    customer,
    lines_data,
    number=None,
    invoice_date=None,
    payment_due=None,
    bank_account=None,
):
    """
    Единственная точка создания счёта.

    lines_data: list[dict] с полями InvoiceLine. Ключ "trip" — объект
    Trip или None (контракт сервиса: объекты, не id).

    number:
        None — автогенерация: внутри atomic select_for_update + Max+1
        с retry-циклом на IntegrityError (защита от гонок).
        int  — явный пользовательский номер: одна попытка, при коллизии
        с unique (account, year, number) — ValidationError под полем.
    """
    account = _require_account(user)
    invoice_date = invoice_date or localdate()
    year = invoice_date.year

    if customer.account_id != account.id:
        raise ValidationError(
            {
                "customer": "Заказчик не принадлежит вашему аккаунту.",
            }
        )
    if bank_account is not None and bank_account.account_id != account.id:
        raise ValidationError(
            {
                "bank_account": "Расчётный счёт не принадлежит вашему аккаунту.",
            }
        )

    trip_ids = [ld["trip"].pk for ld in lines_data if ld.get("trip")]

    user_provided_number = number is not None
    max_attempts = 1 if user_provided_number else 5

    for attempt in range(max_attempts):
        try:
            with transaction.atomic():
                _check_trips_availability(trip_ids, account.id)

                if user_provided_number:
                    invoice_number = number
                else:
                    last_number = (
                        Invoice.objects.select_for_update()
                        .filter(account_id=account.id, year=year)
                        .aggregate(m=Max("number"))["m"]
                        or 0
                    )
                    invoice_number = last_number + 1

                invoice = Invoice(
                    account=account,
                    created_by=user,
                    updated_by=user,
                    year=year,
                    number=invoice_number,
                    date=invoice_date,
                    payment_due=payment_due,
                    customer=customer,
                    bank_account=bank_account,
                )
                invoice.full_clean()
                invoice.save(force_insert=True)

                for ld in lines_data:
                    line = InvoiceLine(invoice=invoice, **ld)
                    line.full_clean()  # → clean() → compute()
                    line.save(force_insert=True)

                return invoice

        except IntegrityError as e:
            if user_provided_number:
                raise ValidationError(
                    {
                        "number": f"Счёт №{number} за {year} год уже существует.",
                    }
                ) from e
            if attempt == max_attempts - 1:
                raise


def update_invoice(invoice, *, user, header_data, lines_diff):
    """
    Редактирование счёта.

    header_data: dict с полями Invoice (date, payment_due, customer, bank_account).
    lines_diff: {"to_create": [...], "to_update": [(pk, {...}), ...], "to_delete": [pk, ...]}

    Порядок внутри atomic():
      1. Блокировка и проверка занятости рейсов (с учётом to_create + to_update)
      2. Обновление шапки
      3. delete → update → create для строк (delete первым, чтобы высвободить
         trip'ы до того как _check_trips_availability увидит их как «занятые»)

    Смена date на другой год запрещена: number привязан к году, перенос
    создаёт дыры в нумерации.

    ProtectedError на delete (будущий PaymentAllocation) конвертируется
    в ValidationError.
    """
    account = _require_account(user)

    if invoice.account_id != account.id:
        raise ValidationError(
            {NON_FIELD_ERRORS: "Счёт не принадлежит вашему аккаунту."}
        )

    new_date = header_data.get("date")
    if new_date and new_date.year != invoice.year:
        raise ValidationError(
            {
                "date": "Смена года счёта требует создания нового счёта. "
                "Удалите текущий и создайте новый с нужной датой.",
            }
        )

    customer = header_data.get("customer")
    if customer is not None and customer.account_id != account.id:
        raise ValidationError({"customer": "Заказчик не принадлежит вашему аккаунту."})

    bank_account = header_data.get("bank_account")
    if bank_account is not None and bank_account.account_id != account.id:
        raise ValidationError(
            {
                "bank_account": "Расчётный счёт не принадлежит вашему аккаунту.",
            }
        )

    # Смена номера: pre-check коллизии (account, year, number).
    # Гонка возможна, но окно узкое — финальная защита через unique
    # constraint на уровне БД.
    new_number = header_data.get("number")
    if new_number is not None and new_number != invoice.number:
        collision = (
            Invoice.objects.filter(
                account_id=account.id, year=invoice.year, number=new_number
            )
            .exclude(pk=invoice.pk)
            .exists()
        )
        if collision:
            raise ValidationError(
                {
                    "number": f"Счёт №{new_number} за {invoice.year} год уже существует.",
                }
            )

    # Рейсы которые останутся или появятся после apply
    trip_ids = []
    for payload in lines_diff["to_create"]:
        if payload.get("trip"):
            trip_ids.append(payload["trip"].pk)
    for _, payload in lines_diff["to_update"]:
        if payload.get("trip"):
            trip_ids.append(payload["trip"].pk)

    with transaction.atomic():
        # 1
        _check_trips_availability(trip_ids, account.id, exclude_invoice=invoice)

        # 2
        for field, value in header_data.items():
            setattr(invoice, field, value)
        invoice.updated_by = user
        invoice.full_clean()
        invoice.save(
            update_fields=[
                *header_data.keys(),
                "updated_by",
                "updated_at",
            ]
        )

        # 3a delete
        if lines_diff["to_delete"]:
            try:
                invoice.lines.filter(pk__in=lines_diff["to_delete"]).delete()
            except ProtectedError as e:
                raise ValidationError(
                    {
                        NON_FIELD_ERRORS: "Нельзя удалить строки, на которые разнесены платежи.",
                    }
                ) from e

        # 3b update
        for pk, payload in lines_diff["to_update"]:
            line = invoice.lines.get(pk=pk)
            for field, value in payload.items():
                setattr(line, field, value)
            line.full_clean()
            line.save()

        # 3c create
        for payload in lines_diff["to_create"]:
            line = InvoiceLine(invoice=invoice, **payload)
            line.full_clean()
            line.save(force_insert=True)


# ─────────────────────────────────────────────────────────────────────
# Payments
# ─────────────────────────────────────────────────────────────────────


def create_payment(
    organization, date, amount, payment_method, direction, created_by, description=""
):
    """
    Регистрирует платёж по контрагенту.

    direction: INCOMING (поступление) или OUTGOING (списание/возврат).
    Платёж привязан к контрагенту, не к счёту или акту.
    """
    if amount <= 0:
        raise ValidationError({"amount": "Сумма платежа должна быть положительной."})

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


def get_counterparty_balances(account, date_from=None, date_to=None):
    """
    Сальдо по контрагентам: начислено (по счетам), оплачено (платежи), долг.

    «Начислено» берётся напрямую из Invoice (через строки счёта), без
    привязки к актам — связь между моделями будет добавлена в отдельной
    итерации.

    Поступления идут со знаком плюс, возвраты (OUTGOING) со знаком минус.
    Период фильтрует по Invoice.date и Payment.date.
    """
    invoice_filter = Q(invoices__account=account)
    incoming_filter = Q(
        payments__account=account,
        payments__direction=PaymentDirection.INCOMING,
    )
    outgoing_filter = Q(
        payments__account=account,
        payments__direction=PaymentDirection.OUTGOING,
    )

    if date_from:
        invoice_filter &= Q(invoices__date__gte=date_from)
        incoming_filter &= Q(payments__date__gte=date_from)
        outgoing_filter &= Q(payments__date__gte=date_from)
    if date_to:
        invoice_filter &= Q(invoices__date__lte=date_to)
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
        .filter(Q(invoices__account=account) | any_payment_filter)
        .annotate(
            invoiced=Coalesce(
                Sum("invoices__lines__amount_total", filter=invoice_filter),
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
        .annotate(paid=F("_incoming") - F("_outgoing"))
        .annotate(balance=F("invoiced") - F("paid"))
        .order_by("-balance", "short_name")
        .distinct()
    )


# ─────────────────────────────────────────────────────────────────────
# Печатная форма счёта (DOCX)
# ─────────────────────────────────────────────────────────────────────


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

        ctx["invoice_number"] = invoice.display_number
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
            vat_rates = {ln.vat_rate for ln in lines if ln.vat_rate and ln.vat_rate > 0}
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
        return f"Счёт {invoice.display_number} от {date_str}.docx"

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
