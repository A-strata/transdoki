from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView

from transdoki.tenancy import get_request_account

from .forms import AccountRegistrationForm, AccountUserCreateForm
from .models import UserProfile


class RegisterView(FormView):
    form_class = AccountRegistrationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("accounts:cabinet")
        return super().dispatch(request, *args, **kwargs)

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

        users_in_account = (
            UserProfile.objects.select_related("user")
            .filter(account=account)
            .order_by("user__username")
        )

        can_manage_users = profile.role in {
            UserProfile.Role.OWNER,
            UserProfile.Role.ADMIN,
        }

        context.update(
            {
                "account": account,
                "profile": profile,
                "users_in_account": users_in_account,
                "can_manage_users": can_manage_users,
            }
        )
        return context


class AccountUserCreateView(LoginRequiredMixin, FormView):
    template_name = "accounts/user_create.html"
    form_class = AccountUserCreateForm
    success_url = reverse_lazy("accounts:user_create")

    def dispatch(self, request, *args, **kwargs):
        self.account = get_request_account(request)
        role = getattr(request.user.profile, "role", None)

        if role not in {UserProfile.Role.OWNER, UserProfile.Role.ADMIN}:
            raise PermissionDenied("Недостаточно прав для создания пользователей.")

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save(
            account=self.account,
            created_by=self.request.user,
        )
        messages.success(
            self.request,
            f"Пользователь {user.username} создан и добавлен в ваш аккаунт.",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["account"] = self.account
        return context
