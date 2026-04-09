import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import BooleanField, Case, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView

from billing.mixins import BillingProtectedMixin
from transdoki.tenancy import get_request_account
from transdoki.views import UserOwnedListView
from trips.models import Trip

from organizations.models import Organization, OrganizationBank
from .models import Act, Invoice, InvoiceLine
from .services import (
    InvoiceGenerator,
    cancel_invoice,
    create_act_from_invoice,
    create_invoice_from_trips,
    prepare_invoice_data,
)


def _get_own_bank_accounts(account):
    """Банковские счета «своей компании» для выбора в счёте."""
    own = Organization.objects.filter(account=account, is_own_company=True).first()
    if not own:
        return OrganizationBank.objects.none()
    return OrganizationBank.objects.filter(
        account_owner=own,
    ).select_related("account_bank")

logger = logging.getLogger(__name__)

INVOICE_SORT_FIELDS = ("date", "number", "customer__short_name")


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

    def _parse_sort(self):
        sort_field = self.request.GET.get("sort", "date").strip()
        sort_dir = self.request.GET.get("dir", "desc").strip()
        if sort_field not in INVOICE_SORT_FIELDS:
            sort_field = "date"
        if sort_dir not in ("asc", "desc"):
            sort_dir = "desc"
        return sort_field, sort_dir

    def get_queryset(self):
        qs = super().get_queryset().select_related("customer")
        today = timezone.localdate()
        qs = qs.annotate(
            is_overdue=Case(
                When(payment_due__lt=today, status=Invoice.Status.SENT, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )

        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(number__icontains=q) | Q(customer__short_name__icontains=q)
            )

        status = self.request.GET.get("status")
        if status and status in Invoice.Status.values:
            qs = qs.filter(status=status)

        if self.request.GET.get("overdue") == "1":
            qs = qs.filter(payment_due__lt=today, status=Invoice.Status.SENT)

        sort_field, sort_dir = self._parse_sort()
        order = sort_field if sort_dir == "asc" else f"-{sort_field}"
        return qs.order_by(order, "-pk")

    def _build_sort_url(self, field, current_sort, current_dir, base_params):
        params = dict(base_params)
        params["sort"] = field
        params["dir"] = (
            "desc" if (field == current_sort and current_dir == "asc") else "asc"
        )
        return "?" + urlencode(params)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        page_obj = ctx.get("page_obj")
        ctx["pagination_items"] = (
            self._build_pagination_items(page_obj) if page_obj else []
        )
        ctx["page_size_options"] = self.page_size_options

        q = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "")
        overdue = self.request.GET.get("overdue", "")
        sort_field, sort_dir = self._parse_sort()
        current_page_size = self.get_paginate_by(self.object_list)

        if q:
            base_qs = super().get_queryset()
            if status and status in Invoice.Status.values:
                base_qs = base_qs.filter(status=status)
            if overdue == "1":
                today = timezone.localdate()
                base_qs = base_qs.filter(payment_due__lt=today, status=Invoice.Status.SENT)
            ctx["total_count"] = base_qs.count()

        ctx["status_choices"] = Invoice.Status.choices
        ctx["filters"] = {
            "q": q,
            "status": status,
            "overdue": overdue,
            "sort": sort_field,
            "dir": sort_dir,
            "page_size": str(current_page_size),
        }

        base_params = {}
        if q:
            base_params["q"] = q
        if status:
            base_params["status"] = status
        if overdue:
            base_params["overdue"] = overdue
        if sort_field != "date":
            base_params["sort"] = sort_field
        if sort_dir != "desc":
            base_params["dir"] = sort_dir
        if str(current_page_size) != str(self.paginate_by):
            base_params["page_size"] = current_page_size
        ctx["query_string"] = ("&" + urlencode(base_params)) if base_params else ""

        ctx["sort_urls"] = {
            f: self._build_sort_url(f, sort_field, sort_dir, base_params)
            for f in INVOICE_SORT_FIELDS
        }

        return ctx


@login_required
def invoice_create(request):
    account = get_request_account(request)

    if request.method == "GET":
        raw_ids = request.GET.get("trip_ids", "") or request.GET.get("trip_id", "")
        trip_ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]

        if not trip_ids:
            messages.error(request, "Не указаны рейсы для создания счёта.")
            return redirect("trips:list")

        try:
            data = prepare_invoice_data(account, trip_ids)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("trips:list")

        bank_accounts = list(_get_own_bank_accounts(account))
        selected_bank_id = bank_accounts[0].pk if bank_accounts else None

        return render(request, "invoicing/invoice_form.html", {
            "customer": data["customer"],
            "lines": data["lines"],
            "trips": data["trips"],
            "invoice_date": data["date"],
            "trip_ids": ",".join(str(t.pk) for t in data["trips"]),
            "vat_rate_choices": InvoiceLine.VatRate.choices,
            "status_choices": Invoice.Status.choices,
            "bank_accounts": bank_accounts,
            "selected_bank_id": selected_bank_id,
            "is_create": True,
            "editable": True,
        })

    raw_ids = request.POST.get("trip_ids", "")
    trip_ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]

    if not trip_ids:
        messages.error(request, "Не указаны рейсы для создания счёта.")
        return redirect("trips:list")

    lines_data = []
    for i, tid in enumerate(trip_ids):
        prefix = f"line_{i}_"
        desc = request.POST.get(f"{prefix}description", "")
        price = request.POST.get(f"{prefix}unit_price", "0")
        disc_amt = request.POST.get(f"{prefix}discount_amount", "0")
        vat = request.POST.get(f"{prefix}vat_rate", "0")
        try:
            unit_price = Decimal(price.replace(",", ".").replace(" ", ""))
        except (InvalidOperation, ValueError):
            unit_price = Decimal("0")
        try:
            discount_amount = Decimal(disc_amt.replace(",", ".").replace(" ", ""))
        except (InvalidOperation, ValueError):
            discount_amount = Decimal("0")
        try:
            vat_rate = int(vat)
        except (ValueError, TypeError):
            vat_rate = 0
        lines_data.append({
            "trip_id": tid,
            "description": desc,
            "unit_price": unit_price,
            "discount_amount": discount_amount,
            "vat_rate": vat_rate,
        })

    invoice_date_raw = request.POST.get("invoice_date", "")
    try:
        invoice_date = date.fromisoformat(invoice_date_raw) if invoice_date_raw else None
    except ValueError:
        invoice_date = None

    payment_due_raw = request.POST.get("payment_due", "")
    try:
        payment_due = date.fromisoformat(payment_due_raw) if payment_due_raw else None
    except ValueError:
        payment_due = None

    invoice_number = request.POST.get("invoice_number", "").strip() or None

    try:
        invoice = create_invoice_from_trips(
            account, trip_ids, request.user,
            invoice_date=invoice_date,
            lines_data=lines_data,
            invoice_number=invoice_number,
        )
        update_fields = []
        if payment_due:
            invoice.payment_due = payment_due
            update_fields.append("payment_due")

        bank_account_id = request.POST.get("bank_account")
        if bank_account_id:
            try:
                invoice.bank_account_id = int(bank_account_id)
                update_fields.append("bank_account")
            except (ValueError, TypeError):
                pass

        if update_fields:
            invoice.save(update_fields=update_fields)
        messages.success(request, f"Создан счёт {invoice.number}.")
        return redirect("invoicing:invoice_detail", pk=invoice.pk)
    except ValueError as e:
        messages.error(request, str(e))
        trips = list(
            Trip.objects.for_account(account)
            .filter(pk__in=trip_ids)
            .prefetch_related("points")
            .select_related("client")
        )
        if not trips:
            return redirect("trips:list")
        trip_map = {t.pk: t for t in trips}
        lines = []
        for ld in lines_data:
            trip = trip_map.get(ld["trip_id"])
            line = InvoiceLine(
                trip=trip,
                kind=InvoiceLine.Kind.SERVICE,
                description=ld["description"],
                unit_price=ld["unit_price"],
                discount_amount=ld["discount_amount"],
                vat_rate=ld["vat_rate"],
            )
            try:
                line.compute()
            except ValueError:
                pass
            lines.append(line)
        bank_accounts = list(_get_own_bank_accounts(account))
        selected_bank_id_raw = request.POST.get("bank_account")
        try:
            selected_bank_id = int(selected_bank_id_raw) if selected_bank_id_raw else (
                bank_accounts[0].pk if bank_accounts else None
            )
        except (ValueError, TypeError):
            selected_bank_id = bank_accounts[0].pk if bank_accounts else None

        return render(request, "invoicing/invoice_form.html", {
            "customer": trips[0].client,
            "lines": lines,
            "trips": trips,
            "invoice_date": invoice_date or date.today(),
            "payment_due": payment_due,
            "trip_ids": ",".join(str(t.pk) for t in trips),
            "vat_rate_choices": InvoiceLine.VatRate.choices,
            "status_choices": Invoice.Status.choices,
            "bank_accounts": bank_accounts,
            "selected_bank_id": selected_bank_id,
            "is_create": True,
            "editable": True,
        })


class InvoiceDetailView(LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = "invoicing/invoice_form.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return Invoice.objects.for_account(
            get_request_account(self.request)
        ).select_related("customer", "bank_account__account_bank")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        invoice = self.object
        account = get_request_account(self.request)
        lines = invoice.lines.select_related("trip").all()
        ctx["lines"] = lines
        ctx["customer"] = invoice.customer
        ctx["has_act"] = hasattr(invoice, "act")
        ctx["vat_rate_choices"] = InvoiceLine.VatRate.choices
        ctx["status_choices"] = Invoice.Status.choices
        can_edit = invoice.status == Invoice.Status.DRAFT
        ctx["can_edit"] = can_edit
        ctx["editable"] = can_edit and self.request.GET.get("edit") == "1"

        bank_accounts = list(_get_own_bank_accounts(account))
        ctx["bank_accounts"] = bank_accounts
        ctx["selected_bank_id"] = invoice.bank_account_id or (
            bank_accounts[0].pk if bank_accounts else None
        )

        ctx["has_discount"] = any(
            l.discount_amount > 0 for l in lines
        )
        ctx["has_vat"] = any(l.vat_rate != 0 for l in lines)
        ctx["totals"] = {
            "gross": sum(l.unit_price for l in lines),
            "discount": sum(l.discount_amount for l in lines),
            "net": sum(l.amount_net for l in lines),
            "vat": sum(l.vat_amount for l in lines),
            "total": sum(l.amount_total for l in lines),
        }
        return ctx


class InvoiceEditView(LoginRequiredMixin, View):

    def post(self, request, pk):
        account = get_request_account(request)
        invoice = get_object_or_404(
            Invoice.objects.for_account(account), pk=pk
        )

        if invoice.status != Invoice.Status.DRAFT:
            messages.error(request, "Редактировать можно только черновик.")
            return redirect("invoicing:invoice_detail", pk=pk)

        lines = list(invoice.lines.all())
        updated = []
        for line in lines:
            prefix = f"line_{line.pk}_"
            desc = request.POST.get(f"{prefix}description")
            price = request.POST.get(f"{prefix}unit_price")
            vat = request.POST.get(f"{prefix}vat_rate")
            disc_amt = request.POST.get(f"{prefix}discount_amount")

            if desc is not None:
                line.description = desc
            if price is not None:
                try:
                    line.unit_price = Decimal(price.replace(",", ".").replace(" ", ""))
                except (InvalidOperation, ValueError):
                    pass
            if vat is not None:
                try:
                    line.vat_rate = int(vat)
                except (ValueError, TypeError):
                    pass
            if disc_amt is not None:
                try:
                    line.discount_amount = Decimal(disc_amt.replace(",", ".").replace(" ", ""))
                except (InvalidOperation, ValueError):
                    line.discount_amount = Decimal("0")

            try:
                line.compute()
            except ValueError as e:
                messages.error(request, str(e))
                return redirect("invoicing:invoice_detail", pk=pk)
            updated.append(line)

        if updated:
            InvoiceLine.objects.bulk_update(
                updated,
                [
                    "description", "unit_price", "discount_pct", "discount_amount",
                    "vat_rate", "amount_net", "vat_amount", "amount_total",
                ],
            )

        invoice_number = request.POST.get("invoice_number", "").strip()
        if invoice_number:
            invoice.number = invoice_number

        invoice_date = request.POST.get("invoice_date")
        if invoice_date is not None:
            try:
                invoice.date = date.fromisoformat(invoice_date) if invoice_date else invoice.date
            except ValueError:
                pass

        payment_due = request.POST.get("payment_due")
        if payment_due is not None:
            try:
                invoice.payment_due = date.fromisoformat(payment_due) if payment_due else None
            except ValueError:
                pass

        bank_account_raw = request.POST.get("bank_account")
        if bank_account_raw is not None:
            try:
                invoice.bank_account_id = int(bank_account_raw) if bank_account_raw else None
            except (ValueError, TypeError):
                pass

        ALLOWED_TRANSITIONS = {
            Invoice.Status.DRAFT: [Invoice.Status.SENT],
            Invoice.Status.SENT:  [Invoice.Status.DRAFT],
        }
        status = request.POST.get("status")
        if status:
            allowed = ALLOWED_TRANSITIONS.get(invoice.status, [])
            if status in allowed:
                invoice.status = status

        invoice.updated_by = request.user
        invoice.save(update_fields=[
            "number", "date", "payment_due", "bank_account",
            "status", "updated_by", "updated_at",
        ])

        return redirect("invoicing:invoice_detail", pk=pk)


class InvoiceCancelView(LoginRequiredMixin, View):

    def post(self, request, pk):
        account = get_request_account(request)
        invoice = get_object_or_404(
            Invoice.objects.for_account(account), pk=pk
        )
        try:
            cancel_invoice(invoice, request.user)
            messages.success(request, f"Счёт {invoice.number} аннулирован.")
        except ValueError as e:
            messages.error(request, str(e))
        return redirect("invoicing:invoice_detail", pk=pk)


class ActCreateView(LoginRequiredMixin, View):

    def post(self, request, pk):
        account = get_request_account(request)
        invoice = get_object_or_404(
            Invoice.objects.for_account(account), pk=pk
        )
        try:
            act = create_act_from_invoice(invoice, request.user)
            messages.success(request, f"Создан акт {act.number}.")
            return redirect("invoicing:act_detail", pk=act.pk)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("invoicing:invoice_detail", pk=pk)


class InvoiceDownloadView(LoginRequiredMixin, View):

    def get(self, request, pk):
        account = get_request_account(request)
        invoice = get_object_or_404(
            Invoice.objects.for_account(account).select_related("customer"), pk=pk
        )
        return InvoiceGenerator.generate_response(invoice)


class ActDetailView(LoginRequiredMixin, DetailView):
    model = Act
    template_name = "invoicing/act_detail.html"
    context_object_name = "act"

    def get_queryset(self):
        return Act.objects.for_account(
            get_request_account(self.request)
        ).select_related("invoice", "invoice__customer")
