import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import FormView, TemplateView

from billing.services.limits import can_create_user
from organizations.models import Organization
from transdoki.tenancy import get_request_account

from .forms import AccountRegistrationForm, AccountUserCreateForm
from .models import UserProfile
from .services import reset_account_user_password

security_logger = logging.getLogger("security")


class ImpersonateStartView(LoginRequiredMixin, View):
    """Суперпользователь начинает просмотр от имени другого пользователя."""

    def post(self, request, user_id):
        if not request.real_user.is_superuser:
            raise PermissionDenied

        from django.contrib.auth import get_user_model
        User = get_user_model()
        target = get_object_or_404(User, pk=user_id)

        if target.is_superuser:
            messages.error(request, "Нельзя войти от имени другого суперпользователя.")
            return redirect(request.META.get("HTTP_REFERER", "admin:index"))

        request.session["_impersonate_user_id"] = target.pk
        security_logger.warning(
            "impersonate_start: superuser %s (%s) → user %s (%s)",
            request.real_user.pk,
            request.real_user.username,
            target.pk,
            target.username,
        )
        messages.success(request, f"Вы работаете от имени {target.get_full_name() or target.username}.")
        return redirect("trips:list")


class ImpersonateStopView(LoginRequiredMixin, View):
    """Прекращение impersonation — возврат к своему аккаунту."""

    def post(self, request):
        if not request.is_impersonating:
            return redirect("trips:list")

        impersonated_username = request.user.username
        del request.session["_impersonate_user_id"]
        security_logger.warning(
            "impersonate_stop: superuser %s (%s) stopped impersonating %s",
            request.real_user.pk,
            request.real_user.username,
            impersonated_username,
        )
        messages.success(request, "Вы вернулись к своему аккаунту.")
        return redirect("admin:index")


class SwitchOrganizationView(LoginRequiredMixin, View):
    def post(self, request):
        account = get_request_account(request)
        org_id = request.POST.get("org_id")
        if org_id:
            org = Organization.objects.own_for(account).filter(pk=org_id).first()
            if org is not None:
                request.session["current_org_id"] = org.pk
                profile = request.user.profile
                if profile.last_active_org_id != org.pk:
                    profile.last_active_org = org
                    profile.save(update_fields=["last_active_org"])
        referer = request.META.get("HTTP_REFERER") or reverse("trips:list")
        return redirect(referer)


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

        own_companies = Organization.objects.own_for(account)

        context.update(
            {
                "account": account,
                "profile": profile,
                "users_in_account": users_in_account,
                "can_manage_users": can_manage_users,
                "own_companies": own_companies,
            }
        )
        return context


class AccountUserCreateView(LoginRequiredMixin, FormView):
    template_name = "accounts/user_create.html"
    form_class = AccountUserCreateForm
    success_url = reverse_lazy("accounts:cabinet")

    def dispatch(self, request, *args, **kwargs):
        self.account = get_request_account(request)
        role = getattr(request.user.profile, "role", None)

        if role not in {UserProfile.Role.OWNER, UserProfile.Role.ADMIN}:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"ok": False, "errors": {"__all__": "Недостаточно прав."}}, status=403)
            raise PermissionDenied("Недостаточно прав для создания пользователей.")

        # Проверка лимита пользователей тарифа. is_billing_exempt и статус
        # подписки проверяются внутри can_create_user.
        ok, msg = can_create_user(self.account)
        if not ok:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"ok": False, "errors": {"__all__": msg}}, status=402,
                )
            messages.error(request, msg)
            return redirect(reverse_lazy("accounts:cabinet"))

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user, temp_password = form.save(account=self.account, created_by=self.request.user)
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({
                "ok": True,
                "username": user.username,
                "temp_password": temp_password,
                "full_name": user.get_full_name() or user.username,
                "role": user.profile.get_role_display(),
            })
        messages.success(
            self.request,
            f"Пользователь {user.username} создан. Временный пароль: {temp_password}",
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            errors = {f: e.get_json_data() for f, e in form.errors.items()}
            return JsonResponse({"ok": False, "errors": {f: msgs[0]["message"] for f, msgs in errors.items()}}, status=400)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["account"] = self.account
        return context


class AccountUserPasswordResetView(LoginRequiredMixin, View):
    def post(self, request, profile_id):
        account = get_request_account(request)
        actor_profile = request.user.profile

        if actor_profile.role not in {UserProfile.Role.OWNER, UserProfile.Role.ADMIN}:
            return JsonResponse({"ok": False, "error": "Недостаточно прав."}, status=403)

        target_profile = get_object_or_404(
            UserProfile.objects.select_related("user").filter(account=account),
            pk=profile_id,
        )

        if target_profile.user_id == request.user.id:
            return JsonResponse({"ok": False, "error": "Нельзя сбросить собственный пароль здесь."}, status=400)

        if target_profile.role == UserProfile.Role.OWNER:
            return JsonResponse({"ok": False, "error": "Нельзя сбросить пароль владельца."}, status=400)

        temp_password = reset_account_user_password(profile=target_profile, actor=request.user)
        return JsonResponse({
            "ok": True,
            "username": target_profile.user.username,
            "temp_password": temp_password,
            "full_name": target_profile.user.get_full_name() or target_profile.user.username,
        })


class AccountUserUpdateView(LoginRequiredMixin, View):
    """AJAX-endpoint: обновляет имя, фамилию и роль пользователя аккаунта."""

    allowed_roles = {
        UserProfile.Role.ADMIN,
        UserProfile.Role.DISPATCHER,
        UserProfile.Role.LOGIST,
    }

    def post(self, request, profile_id):
        if request.headers.get("X-Requested-With") != "XMLHttpRequest":
            raise PermissionDenied

        account = get_request_account(request)
        actor_profile = request.user.profile

        if actor_profile.role not in {UserProfile.Role.OWNER, UserProfile.Role.ADMIN}:
            return JsonResponse({"ok": False, "error": "Недостаточно прав."}, status=403)

        target_profile = get_object_or_404(
            UserProfile.objects.select_related("user").filter(account=account),
            pk=profile_id,
        )

        is_own_profile = target_profile.user_id == request.user.id

        if not is_own_profile and target_profile.role == UserProfile.Role.OWNER:
            return JsonResponse({"ok": False, "error": "Нельзя редактировать владельца аккаунта."}, status=400)

        user = target_profile.user
        user.first_name = request.POST.get("first_name", "").strip()
        user.last_name = request.POST.get("last_name", "").strip()
        user.save(update_fields=["first_name", "last_name"])

        if not is_own_profile:
            new_role = request.POST.get("role")
            if new_role in self.allowed_roles and new_role != target_profile.role:
                target_profile.role = new_role
                target_profile.save(update_fields=["role"])

        return JsonResponse({
            "ok": True,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role_display": target_profile.get_role_display(),
        })


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
