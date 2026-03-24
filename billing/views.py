from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View
from django.views.generic import ListView

from transdoki.tenancy import get_request_account

from .constants import (
    DAILY_RATE_ORG,
    DAILY_RATE_USER,
    DAILY_RATE_VEHICLE,
    FREE_TIER_ORGS,
    FREE_TIER_USERS,
    FREE_TIER_VEHICLES,
)
from .models import BillingTransaction

DAYS_IN_MONTH = 30


class PricingView(View):
    template_name = "pricing.html"

    def get(self, request):
        monthly_org = int(DAILY_RATE_ORG * DAYS_IN_MONTH)
        monthly_vehicle = int(DAILY_RATE_VEHICLE * DAYS_IN_MONTH)
        monthly_user = int(DAILY_RATE_USER * DAYS_IN_MONTH)
        context = {
            "free_orgs": FREE_TIER_ORGS,
            "free_vehicles": FREE_TIER_VEHICLES,
            "free_users": FREE_TIER_USERS,
            "monthly_org": monthly_org,
            "monthly_vehicle": monthly_vehicle,
            "monthly_user": monthly_user,
            "min_paid": min(monthly_org, monthly_vehicle, monthly_user),
        }
        return render(request, self.template_name, context)


class TransactionListView(LoginRequiredMixin, ListView):
    model = BillingTransaction
    template_name = "billing/transaction_list.html"
    context_object_name = "transactions"
    paginate_by = 30

    def get_queryset(self):
        account = get_request_account(self.request)
        return BillingTransaction.objects.filter(account=account).select_related("account")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["account"] = get_request_account(self.request)
        return context
