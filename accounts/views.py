from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
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


class AccountUserRoleUpdateView(LoginRequiredMixin, View):
    allowed_roles = {
        UserProfile.Role.ADMIN,
        UserProfile.Role.DISPATCHER,
        UserProfile.Role.LOGIST,
    }

    def post(self, request, profile_id):
        account = get_request_account(request)
        actor_profile = request.user.profile
        actor_role = actor_profile.role

        if actor_role not in {UserProfile.Role.OWNER, UserProfile.Role.ADMIN}:
            raise PermissionDenied("Недостаточно прав для изменения ролей.")

        target_profile = get_object_or_404(
            UserProfile.objects.select_related("user").filter(account=account),
            pk=profile_id,
        )

        if target_profile.user_id == request.user.id:
            messages.error(request, "Нельзя менять собственную роль.")
            return redirect("accounts:cabinet")

        if (
            actor_role == UserProfile.Role.ADMIN
            and target_profile.role == UserProfile.Role.OWNER
        ):
            raise PermissionDenied("Администратор не может менять роль владельца.")

        if target_profile.role == UserProfile.Role.OWNER:
            messages.error(
                request, "Нельзя менять роль владельца аккаунта в этом разделе."
            )
            return redirect("accounts:cabinet")

        new_role = request.POST.get("role")
        if new_role not in self.allowed_roles:
            messages.error(request, "Некорректная роль.")
            return redirect("accounts:cabinet")

        if target_profile.role == new_role:
            messages.info(request, "Роль не изменилась.")
            return redirect("accounts:cabinet")

        old_role_display = target_profile.get_role_display()
        target_profile.role = new_role
        target_profile.save(update_fields=["role"])
        new_role_display = target_profile.get_role_display()

        messages.success(
            request,
            f"Роль пользователя {target_profile.user.username} изменена: "
            f"{old_role_display} → {new_role_display}.",
        )
        return redirect(f"{reverse('accounts:cabinet')}#user-{target_profile.id}")
