from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView

from transdoki.tenancy import get_request_account

from .forms import AccountRegistrationForm


class RegisterView(FormView):
    form_class = AccountRegistrationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        form.save()
        messages.success(
            self.request,
            "Регистрация завершена. Теперь войдите в систему.",
        )
        return super().form_valid(form)


class AccountCabinetView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/cabinet.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        account = get_request_account(self.request)
        profile = self.request.user.profile

        context.update(
            {
                "account": account,
                "profile": profile,
            }
        )
        return context
