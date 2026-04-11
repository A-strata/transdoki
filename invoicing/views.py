import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import BooleanField, Case, Q, Sum, Value, When
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
from .models import Act, Invoice, InvoiceLine, Payment, PaymentDirection, PaymentMethod
from .services import (
    InvoiceGenerator,
    cancel_invoice,
    create_act_from_invoice,
    create_invoice_from_trips,
    get_counterparty_balances,
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
        lookups = (
            Q(number__icontains=q)
            | Q(customer__short_name__icontains=q)
        )
        # Поиск по сумме: если введено число, ищем по total строк
        # Приводим total к строке через Cast и ищем вхождение
        cleaned = q.replace(",", ".").replace(" ", "")
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
            lookups = lookups | Q(pk__in=matching_pks)
        except (InvalidOperation, ValueError):
            pass
        return qs.filter(lookups)

    def _apply_date_filters(self, qs):
        date_from = self._normalize_date_value(self.request.GET.get("date_from"))
        date_to = self._normalize_date_value(self.request.GET.get("date_to"))

        if not date_from and not date_to:
            return qs

        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        return qs

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

        qs = self._apply_search(qs)
        qs = self._apply_date_filters(qs)

        return qs.order_by("-date", "-pk")

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
            "unit_choices": InvoiceLine.UnitOfMeasure.choices,
            "status_choices": Invoice.Status.choices,
            "bank_accounts": bank_accounts,
            "selected_bank_id": selected_bank_id,
            "is_create": True,
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
        vat = request.POST.get(f"{prefix}vat_rate", "")
        qty_raw = request.POST.get(f"{prefix}quantity", "1")
        unit_val = request.POST.get(f"{prefix}unit", InvoiceLine.UnitOfMeasure.SERVICE)
        try:
            unit_price = Decimal(price.replace(",", ".").replace(" ", ""))
        except (InvalidOperation, ValueError):
            unit_price = Decimal("0")
        try:
            discount_amount = Decimal(disc_amt.replace(",", ".").replace(" ", ""))
        except (InvalidOperation, ValueError):
            discount_amount = Decimal("0")
        try:
            quantity = Decimal(qty_raw.replace(",", ".").replace(" ", ""))
            if quantity <= 0:
                quantity = Decimal("1")
        except (InvalidOperation, ValueError):
            quantity = Decimal("1")
        if vat == "":
            vat_rate = None
        else:
            try:
                vat_rate = int(vat)
            except (ValueError, TypeError):
                vat_rate = None
        lines_data.append({
            "trip_id": tid,
            "description": desc,
            "unit_price": unit_price,
            "quantity": quantity,
            "unit": unit_val,
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
                quantity=ld.get("quantity", Decimal("1")),
                unit=ld.get("unit", InvoiceLine.UnitOfMeasure.SERVICE),
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
            "unit_choices": InvoiceLine.UnitOfMeasure.choices,
            "status_choices": Invoice.Status.choices,
            "bank_accounts": bank_accounts,
            "selected_bank_id": selected_bank_id,
            "is_create": True,
        })


class InvoiceDetailView(LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = "invoicing/invoice_detail.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return Invoice.objects.for_account(
            get_request_account(self.request)
        ).select_related("customer", "bank_account__account_bank")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        invoice = self.object
        lines = list(invoice.lines.select_related("trip").all())
        ctx["lines"] = lines
        ctx["customer"] = invoice.customer
        ctx["has_act"] = hasattr(invoice, "act")
        ctx["can_edit"] = invoice.status != Invoice.Status.CANCELLED

        ctx["has_discount"] = any(
            l.discount_amount > 0 for l in lines
        )
        vat_rates = set(l.vat_rate for l in lines if l.vat_rate is not None)
        ctx["has_vat"] = bool(vat_rates)
        ctx["vat_rate_display"] = f"{vat_rates.pop()}%" if len(vat_rates) == 1 else "смеш."
        ctx["totals"] = {
            "gross": sum(l.unit_price * l.quantity for l in lines),
            "discount": sum(l.discount_amount for l in lines),
            "net": sum(l.amount_net for l in lines),
            "vat": sum(l.vat_amount for l in lines),
            "total": sum(l.amount_total for l in lines),
        }
        return ctx


class InvoiceEditView(LoginRequiredMixin, View):

    def get(self, request, pk):
        account = get_request_account(request)
        invoice = get_object_or_404(
            Invoice.objects.for_account(account)
            .select_related("customer", "bank_account__account_bank"),
            pk=pk,
        )
        lines = list(invoice.lines.select_related("trip").all())
        bank_accounts = list(_get_own_bank_accounts(account))

        has_discount = any(l.discount_amount > 0 for l in lines)
        vat_rates = set(l.vat_rate for l in lines if l.vat_rate is not None)

        return render(request, "invoicing/invoice_form.html", {
            "invoice": invoice,
            "customer": invoice.customer,
            "lines": lines,
            "vat_rate_choices": InvoiceLine.VatRate.choices,
            "unit_choices": InvoiceLine.UnitOfMeasure.choices,
            "status_choices": Invoice.Status.choices,
            "bank_accounts": bank_accounts,
            "selected_bank_id": invoice.bank_account_id or (
                bank_accounts[0].pk if bank_accounts else None
            ),
            "has_discount": has_discount,
            "has_vat": bool(vat_rates),
            "vat_rate_display": f"{vat_rates.pop()}%" if len(vat_rates) == 1 else "смеш.",
            "totals": {
                "gross": sum(l.unit_price * l.quantity for l in lines),
                "discount": sum(l.discount_amount for l in lines),
                "net": sum(l.amount_net for l in lines),
                "vat": sum(l.vat_amount for l in lines),
                "total": sum(l.amount_total for l in lines),
            },
        })

    def post(self, request, pk):
        account = get_request_account(request)
        invoice = get_object_or_404(
            Invoice.objects.for_account(account), pk=pk
        )

        lines = list(invoice.lines.all())
        updated = []
        for line in lines:
            prefix = f"line_{line.pk}_"
            desc = request.POST.get(f"{prefix}description")
            price = request.POST.get(f"{prefix}unit_price")
            qty_raw = request.POST.get(f"{prefix}quantity")
            unit_val = request.POST.get(f"{prefix}unit")
            vat = request.POST.get(f"{prefix}vat_rate")
            disc_amt = request.POST.get(f"{prefix}discount_amount")

            if desc is not None:
                line.description = desc
            if price is not None:
                try:
                    line.unit_price = Decimal(price.replace(",", ".").replace(" ", ""))
                except (InvalidOperation, ValueError):
                    pass
            if qty_raw is not None:
                try:
                    qty = Decimal(qty_raw.replace(",", ".").replace(" ", ""))
                    if qty > 0:
                        line.quantity = qty
                except (InvalidOperation, ValueError):
                    pass
            if unit_val is not None:
                line.unit = unit_val
            if vat is not None:
                if vat == "":
                    line.vat_rate = None
                else:
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
                    "description", "unit_price", "quantity", "unit",
                    "discount_pct", "discount_amount",
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
            Invoice.Status.SENT:  [Invoice.Status.DRAFT, Invoice.Status.PAID],
            Invoice.Status.PAID:  [Invoice.Status.SENT],
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

    def get(self, request, org_pk):
        account = get_request_account(request)
        org = get_object_or_404(
            Organization.objects.for_account(account), pk=org_pk
        )

        acts = list(
            Act.objects.filter(
                account=account,
                invoice__customer=org,
                status=Act.Status.SIGNED,
            ).select_related("invoice").order_by("date", "pk")
        )

        payments = list(
            Payment.objects.filter(
                account=account,
                organization=org,
            ).order_by("date", "pk")
        )

        timeline = []
        for act in acts:
            timeline.append({
                "date": act.date,
                "type": "act",
                "label": f"Акт {act.number}",
                "act": act,
                "invoiced": act.amount_total,
                "paid": None,
            })
        for p in payments:
            timeline.append({
                "date": p.date,
                "type": "payment",
                "label": f"Платёж",
                "payment": p,
                "invoiced": None,
                "paid": p.amount,
            })

        timeline.sort(key=lambda e: (e["date"], 0 if e["type"] == "act" else 1))

        running_balance = Decimal("0")
        for entry in timeline:
            if entry["invoiced"]:
                running_balance += entry["invoiced"]
            if entry["paid"]:
                running_balance -= entry["paid"]
            entry["balance"] = running_balance

        total_invoiced = sum(a.amount_total for a in acts)
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
