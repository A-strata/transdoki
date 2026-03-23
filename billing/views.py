from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from transdoki.tenancy import get_request_account

from .models import BillingTransaction


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
