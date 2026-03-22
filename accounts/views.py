from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import FormView

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
