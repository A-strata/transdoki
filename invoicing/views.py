from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView

from organizations.models import Organization
from transdoki.enums import VatRate
from transdoki.tenancy import get_request_account
from transdoki.views import UserOwnedListView

from .forms import (
    LINE_META_KEYS,
    InvoiceForm,
    InvoiceLineFormSet,
    InvoiceLineFormSetNew,
)
from .models import Invoice, InvoiceLine, Payment, PaymentMethod
from .services import (
    InvoiceGenerator,
    create_invoice,
    get_counterparty_balances,
    prepare_invoice_data,
    update_invoice,
)

# ─────────────────────────────────────────────────────────────────────
# Формсет-хелперы
# ─────────────────────────────────────────────────────────────────────

def _formset_to_lines_data(formset):
    """
    Create-ветка: плоский list[dict] всех не-DELETE строк.

    Используется только в InvoiceCreateView, где новых строк всегда
    несколько, существующих нет — diff не нужен.
    """
    return [
        {k: v for k, v in f.cleaned_data.items() if k not in LINE_META_KEYS}
        for f in formset
        if f.cleaned_data and not f.cleaned_data.get("DELETE")
    ]


def _formset_to_lines_diff(formset):
    """
    Edit-ветка: раскладывает формсет на три группы для update_invoice.

    Возвращает:
        to_create: list[dict]       — новые строки без id
        to_update: list[(pk, dict)] — существующие без DELETE
        to_delete: list[pk]         — существующие с DELETE=True

    'id' в cleaned_data — объект InvoiceLine (ModelChoiceField),
    не int. Берём .pk.
    """
    to_create, to_update, to_delete = [], [], []

    for f in formset:
        if not f.cleaned_data:
            continue

        instance = f.cleaned_data.get("id")  # InvoiceLine | None
        is_delete = f.cleaned_data.get("DELETE", False)

        if is_delete:
            if instance:
                to_delete.append(instance.pk)
            continue

        payload = {
            k: v for k, v in f.cleaned_data.items() if k not in LINE_META_KEYS
        }

        if instance:
            to_update.append((instance.pk, payload))
        else:
            to_create.append(payload)

    return {"to_create": to_create, "to_update": to_update, "to_delete": to_delete}


def _apply_service_errors(exc, form):
    """
    Раскладывает ValidationError из сервиса по полям формы.

    NON_FIELD_ERRORS → non_field_errors формы.
    Ключи, совпадающие с полями формы → под поле.
    Остальные → non_field_errors.
    """
    if hasattr(exc, "message_dict"):
        for field, errs in exc.message_dict.items():
            target = (
                field
                if field != NON_FIELD_ERRORS and field in form.fields
                else None
            )
            form.add_error(target, errs)
    else:
        form.add_error(None, exc)


# ─────────────────────────────────────────────────────────────────────
# Invoice list
# ─────────────────────────────────────────────────────────────────────

class InvoiceListView(UserOwnedListView):
    model = Invoice
    template_name = "invoicing/invoice_list.html"
    partial_template_name = "invoicing/invoice_list_table.html"
    context_object_name = "invoices"
    paginate_by = 25
    page_size_options = [25, 50, 100]

    def get_template_names(self):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return [self.partial_template_name]
        return [self.template_name]

    def _normalize_date_value(self, value):
        value = (value or "").strip()
        return value or None

    def _apply_search(self, qs):
        q = self.request.GET.get("q", "").strip()
        if not q:
            return qs

        lookups = Q(customer__short_name__icontains=q)

        cleaned = q.replace(",", ".").replace(" ", "")

        # Поиск по номеру (целое число)
        if cleaned.isdigit():
            lookups |= Q(number=int(cleaned))

        # Поиск по сумме счёта
        try:
            Decimal(cleaned)
            from django.db.models import CharField
            from django.db.models.functions import Cast
            matching_pks = (
                Invoice.objects.annotate(
                    _total=Sum("lines__amount_total"),
                    _total_str=Cast("_total", CharField()),
                )
                .filter(_total_str__contains=cleaned)
                .values("pk")
            )
            lookups |= Q(pk__in=matching_pks)
        except (InvalidOperation, ValueError):
            pass

        return qs.filter(lookups)

    def _apply_date_filters(self, qs):
        date_from = self._normalize_date_value(self.request.GET.get("date_from"))
        date_to = self._normalize_date_value(self.request.GET.get("date_to"))

        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        return qs

    def get_queryset(self):
        qs = super().get_queryset().select_related("customer", "seller")
        current_org = getattr(self.request, "current_org", None)
        if current_org is None:
            qs = qs.none()
        else:
            qs = qs.filter(seller=current_org)
        qs = self._apply_search(qs)
        qs = self._apply_date_filters(qs)
        return qs.order_by("-year", "-number")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        page_obj = ctx.get("page_obj")
        ctx["pagination_items"] = (
            self._build_pagination_items(page_obj) if page_obj else []
        )
        ctx["page_size_options"] = self.page_size_options

        q = self.request.GET.get("q", "").strip()
        current_page_size = self.get_paginate_by(self.object_list)

        ctx["filters"] = {
            "q": q,
            "date_from": (self.request.GET.get("date_from") or "").strip(),
            "date_to": (self.request.GET.get("date_to") or "").strip(),
            "page_size": str(current_page_size),
        }

        base_params = {}
        if q:
            base_params["q"] = q
        if ctx["filters"]["date_from"]:
            base_params["date_from"] = ctx["filters"]["date_from"]
        if ctx["filters"]["date_to"]:
            base_params["date_to"] = ctx["filters"]["date_to"]
        if str(current_page_size) != str(self.paginate_by):
            base_params["page_size"] = current_page_size
        ctx["query_string"] = ("&" + urlencode(base_params)) if base_params else ""

        return ctx


# ─────────────────────────────────────────────────────────────────────
# Invoice create
# ─────────────────────────────────────────────────────────────────────

class InvoiceCreateView(LoginRequiredMixin, View):

    template_name = "invoicing/invoice_form.html"

    def _render(self, request, form, formset, *, trip_ids=""):
        return render(request, self.template_name, {
            "form": form,
            "formset": formset,
            "is_create": True,
            "trip_ids": trip_ids,
            "vat_rate_choices": VatRate.choices,
            "unit_choices": InvoiceLine.UnitOfMeasure.choices,
        })

    def get(self, request):
        account = get_request_account(request)
        current_org = getattr(request, "current_org", None)

        raw_ids = request.GET.get("trip_ids", "") or request.GET.get("trip_id", "")
        trip_ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]

        initial_header = {"date": date.today()}
        initial_lines = []
        prefilled_trips = []

        if trip_ids:
            try:
                data = prepare_invoice_data(
                    request.user, trip_ids, current_org=current_org
                )
            except ValidationError as e:
                msgs = (
                    e.message_dict.get(NON_FIELD_ERRORS, [str(e)])
                    if hasattr(e, "message_dict")
                    else [str(e)]
                )
                for m in msgs:
                    messages.error(request, m)
                if len(trip_ids) == 1:
                    return redirect("trips:detail", pk=trip_ids[0])
                return redirect("trips:list")

            initial_lines = data["lines"]
            initial_header["customer"] = data["customer"]
            prefilled_trips = [ld["trip"] for ld in initial_lines]

        form = InvoiceForm(initial=initial_header, account=account, current_org=current_org)
        formset = InvoiceLineFormSetNew(initial=initial_lines, prefix="lines")

        return self._render(
            request, form, formset,
            trip_ids=",".join(str(t.pk) for t in prefilled_trips),
        )

    def post(self, request):
        account = get_request_account(request)
        current_org = getattr(request, "current_org", None)
        form = InvoiceForm(request.POST, account=account, current_org=current_org)
        formset = InvoiceLineFormSetNew(request.POST, prefix="lines")

        if form.is_valid() and formset.is_valid():
            try:
                invoice = create_invoice(
                    user=request.user,
                    customer=form.cleaned_data["customer"],
                    seller=form.cleaned_data["seller"],
                    lines_data=_formset_to_lines_data(formset),
                    number=form.cleaned_data.get("number"),  # None → автогенерация
                    invoice_date=form.cleaned_data["date"],
                    payment_due=form.cleaned_data.get("payment_due"),
                    bank_account=form.cleaned_data.get("bank_account"),
                )
                messages.success(request, f"Создан счёт {invoice.display_number}.")
                return redirect("invoicing:invoice_detail", pk=invoice.pk)
            except ValidationError as e:
                _apply_service_errors(e, form)

        return self._render(
            request, form, formset,
            trip_ids=request.POST.get("trip_ids", ""),
        )


# ─────────────────────────────────────────────────────────────────────
# Invoice detail
# ─────────────────────────────────────────────────────────────────────

class InvoiceDetailView(LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = "invoicing/invoice_detail.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return Invoice.objects.for_account(
            get_request_account(self.request)
        ).select_related("seller", "customer", "bank_account__account_bank")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        invoice = self.object
        lines = list(invoice.lines.select_related("trip").all())
        ctx["lines"] = lines
        ctx["customer"] = invoice.customer

        current_org = getattr(self.request, "current_org", None)
        ctx["can_edit"] = (
            invoice.seller_id is not None
            and current_org is not None
            and invoice.seller_id == current_org.pk
        )

        ctx["has_discount"] = any(line.discount_amount > 0 for line in lines)
        vat_rates = {line.vat_rate for line in lines if line.vat_rate is not None}
        ctx["has_vat"] = bool(vat_rates)
        if len(vat_rates) == 1:
            ctx["vat_rate_display"] = f"{vat_rates.pop()}%"
        elif len(vat_rates) > 1:
            ctx["vat_rate_display"] = "смеш."
        else:
            ctx["vat_rate_display"] = "—"

        ctx["totals"] = {
            "gross": sum(line.unit_price * line.quantity for line in lines),
            "discount": sum(line.discount_amount for line in lines),
            "net": sum(line.amount_net for line in lines),
            "vat": sum(line.vat_amount for line in lines),
            "total": sum(line.amount_total for line in lines),
        }
        return ctx


# ─────────────────────────────────────────────────────────────────────
# Invoice edit
# ─────────────────────────────────────────────────────────────────────

class InvoiceEditView(LoginRequiredMixin, View):

    template_name = "invoicing/invoice_form.html"

    def _get_invoice(self, request, pk):
        return get_object_or_404(
            Invoice.objects
            .for_account(get_request_account(request))
            .select_related("seller", "customer", "bank_account__account_bank"),
            pk=pk,
        )

    def _guard_current_org(self, request, invoice):
        """
        Запрещает редактирование счёта, если текущая своя фирма
        пользователя не совпадает с invoice.seller. Возвращает
        HttpResponse-редирект на detail или None, если всё ОК.

        Invoice.seller NOT NULL гарантируется на уровне БД
        (миграция 0015), поэтому здесь проверяем только current_org.
        """
        current_org = getattr(request, "current_org", None)
        if current_org is None or current_org.pk != invoice.seller_id:
            messages.error(
                request,
                f"Для редактирования счёта {invoice.display_number} "
                f"переключитесь на фирму «{invoice.seller.short_name}».",
            )
            return redirect("invoicing:invoice_detail", pk=invoice.pk)
        return None

    def _render(self, request, invoice, form, formset):
        existing_lines = list(invoice.lines.select_related("trip").all())
        has_discount = any(line.discount_amount > 0 for line in existing_lines)
        vat_rates = {line.vat_rate for line in existing_lines if line.vat_rate is not None}

        if len(vat_rates) == 1:
            vat_rate_display = f"{vat_rates.pop()}%"
        elif len(vat_rates) > 1:
            vat_rate_display = "смеш."
        else:
            vat_rate_display = "—"

        return render(request, self.template_name, {
            "invoice": invoice,
            "customer": invoice.customer,
            "form": form,
            "formset": formset,
            "has_discount": has_discount,
            "has_vat": bool(vat_rates),
            "vat_rate_display": vat_rate_display,
            "vat_rate_choices": VatRate.choices,
            "unit_choices": InvoiceLine.UnitOfMeasure.choices,
            "totals": {
                "gross": sum(line.unit_price * line.quantity for line in existing_lines),
                "discount": sum(line.discount_amount for line in existing_lines),
                "net": sum(line.amount_net for line in existing_lines),
                "vat": sum(line.vat_amount for line in existing_lines),
                "total": sum(line.amount_total for line in existing_lines),
            },
        })

    def get(self, request, pk):
        invoice = self._get_invoice(request, pk)
        guard = self._guard_current_org(request, invoice)
        if guard is not None:
            return guard
        account = get_request_account(request)
        current_org = getattr(request, "current_org", None)
        form = InvoiceForm(instance=invoice, account=account, current_org=current_org)
        formset = InvoiceLineFormSet(instance=invoice, prefix="lines")
        return self._render(request, invoice, form, formset)

    def post(self, request, pk):
        invoice = self._get_invoice(request, pk)
        guard = self._guard_current_org(request, invoice)
        if guard is not None:
            return guard
        account = get_request_account(request)
        current_org = getattr(request, "current_org", None)
        form = InvoiceForm(
            request.POST, instance=invoice, account=account, current_org=current_org
        )
        formset = InvoiceLineFormSet(request.POST, instance=invoice, prefix="lines")

        if form.is_valid() and formset.is_valid():
            header_data = dict(form.cleaned_data)
            # Если пользователь очистил поле "номер" — не трогаем его:
            # сохраняется исходное значение invoice.number.
            if header_data.get("number") is None:
                header_data.pop("number", None)
            try:
                update_invoice(
                    invoice,
                    user=request.user,
                    header_data=header_data,
                    lines_diff=_formset_to_lines_diff(formset),
                )
                messages.success(request, f"Счёт {invoice.display_number} обновлён.")
                return redirect("invoicing:invoice_detail", pk=invoice.pk)
            except ValidationError as e:
                _apply_service_errors(e, form)

        return self._render(request, invoice, form, formset)


# ─────────────────────────────────────────────────────────────────────
# Invoice delete
# ─────────────────────────────────────────────────────────────────────

class InvoiceLineUnbindView(LoginRequiredMixin, View):
    """
    Отвязывает строку счёта от рейса (фактически удаляет строку).

    Сценарий: из карточки рейса пользователь хочет «отцепить» рейс
    от уже выставленного счёта — например, если собирается его
    перевыставить или включить в другой счёт.

    Изоляция: строку берём через invoice.account_id (tenant) и
    проверяем что текущая своя фирма == invoice.seller (как в
    InvoiceEditView._guard_current_org).

    Edge case «последняя строка счёта»: если после удаления в счёте
    не остаётся ни одной строки — удаляем сам счёт целиком, чтобы не
    оставлять «пустышки» в списке и не нарушать бизнес-смысл.
    Номер счёта при этом «выгорает» — это осознанная плата за простоту
    UI (пересоздание номеров ломает сквозную нумерацию и аудит).

    Редирект: по параметру next=, иначе — на detail счёта. next
    валидируется — допускается только относительный путь внутри
    сайта (без схемы и домена), иначе open redirect.
    """

    def post(self, request, pk):
        account = get_request_account(request)
        line = get_object_or_404(
            InvoiceLine.objects.select_related("invoice", "invoice__seller")
            .filter(invoice__account=account),
            pk=pk,
        )
        invoice = line.invoice

        current_org = getattr(request, "current_org", None)
        if current_org is None or current_org.pk != invoice.seller_id:
            messages.error(
                request,
                f"Для изменения счёта {invoice.display_number} "
                f"переключитесь на фирму «{invoice.seller.short_name}».",
            )
            return redirect("invoicing:invoice_detail", pk=invoice.pk)

        display = invoice.display_number
        remaining = invoice.lines.exclude(pk=line.pk).count()

        try:
            if remaining == 0:
                # Пустой счёт бессмысленен — удаляем целиком.
                invoice.delete()
                messages.success(
                    request,
                    f"Счёт {display} удалён (в нём была одна строка).",
                )
            else:
                update_invoice(
                    invoice,
                    user=request.user,
                    header_data={},
                    lines_diff={
                        "to_create": [],
                        "to_update": [],
                        "to_delete": [line.pk],
                    },
                )
                messages.success(
                    request, f"Рейс отвязан от счёта {display}."
                )
        except ValidationError as exc:
            if hasattr(exc, "message_dict"):
                for errs in exc.message_dict.values():
                    for msg in errs:
                        messages.error(request, msg)
            else:
                messages.error(request, str(exc))
            return redirect("invoicing:invoice_detail", pk=invoice.pk)

        # Безопасный redirect по next= или на detail счёта.
        next_url = request.POST.get("next", "")
        if next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)
        if remaining == 0:
            return redirect("invoicing:invoice_list")
        return redirect("invoicing:invoice_detail", pk=invoice.pk)


class InvoiceDeleteView(LoginRequiredMixin, View):

    def post(self, request, pk):
        account = get_request_account(request)
        invoice = get_object_or_404(
            Invoice.objects.for_account(account).select_related("seller"), pk=pk
        )
        current_org = getattr(request, "current_org", None)
        if current_org is None or invoice.seller_id != current_org.pk:
            messages.error(
                request,
                f"Для удаления счёта {invoice.display_number} "
                f"переключитесь на фирму «{invoice.seller.short_name}».",
            )
            return redirect("invoicing:invoice_detail", pk=invoice.pk)

        display = invoice.display_number
        invoice.delete()
        messages.success(request, f"Счёт {display} удалён.")
        return redirect("invoicing:invoice_list")


# ─────────────────────────────────────────────────────────────────────
# Invoice download (DOCX)
# ─────────────────────────────────────────────────────────────────────

class InvoiceDownloadView(LoginRequiredMixin, View):

    def get(self, request, pk):
        account = get_request_account(request)
        invoice = get_object_or_404(
            Invoice.objects.for_account(account).select_related("customer"), pk=pk
        )
        return InvoiceGenerator.generate_response(invoice)


# ─────────────────────────────────────────────────────────────────────
# Settlements
# ─────────────────────────────────────────────────────────────────────

class SettlementsView(LoginRequiredMixin, View):

    def get(self, request):
        account = get_request_account(request)

        date_from = request.GET.get("date_from")
        date_to = request.GET.get("date_to")
        hide_zero = request.GET.get("hide_zero") == "1"

        parsed_from = None
        parsed_to = None
        if date_from:
            try:
                parsed_from = date.fromisoformat(date_from)
            except ValueError:
                pass
        if date_to:
            try:
                parsed_to = date.fromisoformat(date_to)
            except ValueError:
                pass

        qs = get_counterparty_balances(account, date_from=parsed_from, date_to=parsed_to)
        if hide_zero:
            qs = qs.exclude(balance=0)

        total_invoiced = sum(row.invoiced for row in qs)
        total_paid = sum(row.paid for row in qs)
        total_balance = total_invoiced - total_paid

        return render(request, "invoicing/settlements.html", {
            "rows": qs,
            "filters": {
                "date_from": date_from or "",
                "date_to": date_to or "",
                "hide_zero": hide_zero,
            },
            "totals": {
                "invoiced": total_invoiced,
                "paid": total_paid,
                "balance": total_balance,
            },
        })


class SettlementDetailView(LoginRequiredMixin, View):
    """
    Детальная страница сальдо по контрагенту.

    Timeline строится из Invoice (начисления) и Payment (платежи).
    Акты не участвуют — связь между моделями будет добавлена в отдельной
    итерации.
    """

    def get(self, request, org_pk):
        account = get_request_account(request)
        org = get_object_or_404(
            Organization.objects.for_account(account), pk=org_pk
        )

        invoices = list(
            Invoice.objects
            .for_account(account)
            .filter(customer=org)
            .prefetch_related("lines")
            .order_by("date", "pk")
        )

        payments = list(
            Payment.objects.filter(
                account=account,
                organization=org,
            ).order_by("date", "pk")
        )

        timeline = []
        for inv in invoices:
            timeline.append({
                "date": inv.date,
                "type": "invoice",
                "label": f"Счёт {inv.display_number}",
                "invoice": inv,
                "invoiced": inv.total,
                "paid": None,
            })
        for p in payments:
            timeline.append({
                "date": p.date,
                "type": "payment",
                "label": "Платёж",
                "payment": p,
                "invoiced": None,
                "paid": p.amount,
            })

        timeline.sort(key=lambda e: (e["date"], 0 if e["type"] == "invoice" else 1))

        running_balance = Decimal("0")
        for entry in timeline:
            if entry["invoiced"]:
                running_balance += entry["invoiced"]
            if entry["paid"]:
                running_balance -= entry["paid"]
            entry["balance"] = running_balance

        total_invoiced = sum(inv.total for inv in invoices)
        total_paid = sum(p.amount for p in payments)

        return render(request, "invoicing/settlement_detail.html", {
            "org": org,
            "timeline": timeline,
            "totals": {
                "invoiced": total_invoiced,
                "paid": total_paid,
                "balance": total_invoiced - total_paid,
            },
            "payment_methods": PaymentMethod.choices,
        })
