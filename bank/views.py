from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views import View

from organizations.models import Organization
from transdoki.tenancy import get_request_account

from invoicing.models import Payment, PaymentDirection, PaymentMethod
from invoicing.services import create_payment, delete_payment


class BankStatementView(LoginRequiredMixin, View):

    def get(self, request):
        account = get_request_account(request)

        date_from = request.GET.get("date_from", "")
        date_to = request.GET.get("date_to", "")
        direction = request.GET.get("direction", "")
        q = request.GET.get("q", "")

        qs = Payment.objects.filter(account=account).select_related("organization")

        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        if direction in (PaymentDirection.INCOMING, PaymentDirection.OUTGOING):
            qs = qs.filter(direction=direction)
        if q:
            qs = qs.filter(organization__short_name__icontains=q)

        qs = qs.order_by("-date", "-pk")
        payments = list(qs)

        total_incoming = sum(p.amount for p in payments if p.direction == PaymentDirection.INCOMING)
        total_outgoing = sum(p.amount for p in payments if p.direction == PaymentDirection.OUTGOING)

        context = {
            "payments": payments,
            "filters": {
                "date_from": date_from,
                "date_to": date_to,
                "direction": direction,
                "q": q,
            },
            "totals": {
                "incoming": total_incoming,
                "outgoing": total_outgoing,
                "balance": total_incoming - total_outgoing,
            },
            "direction_choices": PaymentDirection.choices,
            "method_choices": PaymentMethod.choices,
        }

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return render(request, "bank/statement_table.html", context)

        return render(request, "bank/statement.html", context)


class PaymentCreateView(LoginRequiredMixin, View):

    def post(self, request):
        account = get_request_account(request)

        org_pk = request.POST.get("organization")
        org = get_object_or_404(
            Organization.objects.for_account(account), pk=org_pk
        )

        try:
            payment_date = request.POST.get("payment_date")
            amount = request.POST.get("amount", "").replace(",", ".").replace("\u00a0", "")
            payment_method = request.POST.get("payment_method", PaymentMethod.BANK_TRANSFER)
            direction = request.POST.get("direction", PaymentDirection.INCOMING)
            description = request.POST.get("description", "")

            if not payment_date or not amount:
                raise ValueError("Укажите дату и сумму платежа.")

            create_payment(
                organization=org,
                date=payment_date,
                amount=Decimal(amount),
                payment_method=payment_method,
                direction=direction,
                created_by=request.user,
                description=description,
            )
            messages.success(request, "Платёж зарегистрирован.")
        except (ValueError, InvalidOperation) as e:
            messages.error(request, str(e))

        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("bank:statement")


class PaymentDeleteView(LoginRequiredMixin, View):

    def post(self, request, pk):
        account = get_request_account(request)
        payment = get_object_or_404(
            Payment.objects.filter(account=account), pk=pk
        )
        delete_payment(payment)
        messages.success(request, "Платёж удалён.")

        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("bank:statement")
