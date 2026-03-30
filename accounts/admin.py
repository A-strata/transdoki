import logging

from django.contrib import admin, messages
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.shortcuts import redirect

from .models import Account, UserProfile, UserSession

security_logger = logging.getLogger("security")


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """Управление аккаунтами и биллингом."""

    list_display = (
        "name",
        "owner",
        "balance",
        "is_billing_exempt",
        "is_active",
        "created_at",
    )
    list_editable = ("is_billing_exempt", "is_active")
    search_fields = ("name", "owner__username", "owner__email")
    list_filter = ("is_active", "is_billing_exempt")
    raw_id_fields = ("owner",)
    fieldsets = (
        (None, {
            "fields": ("name", "owner", "is_active"),
        }),
        ("Биллинг", {
            "fields": ("balance", "is_billing_exempt", "credit_limit"),
        }),
        ("Бесплатный уровень", {
            "fields": ("free_orgs", "free_vehicles", "free_users"),
        }),
    )


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Бизнес-профиль"
    extra = 0
    # Выводим account и role для редактирования,
    # а лимиты аккаунта — только для информации (readonly)
    fields = ("account", "role")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "account_display", "role_display")
    search_fields = ("user__username", "user__email")
    list_select_related = ("user", "account")
    list_filter = ("role", "account")

    @admin.display(description="Аккаунт")
    def account_display(self, obj):
        return obj.account or "—"

    @admin.display(description="Роль")
    def role_display(self, obj):
        return obj.get_role_display()


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "session_key", "last_activity", "is_active")
    list_filter = ("is_active", "user")
    search_fields = ("session_key", "user__username")
    list_select_related = ("user",)


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = (
        "username",
        "email",
        "role_display",
        "account_display",
        "is_staff",
        "is_active",
    )
    actions = ["impersonate_user"]

    @admin.display(description="Роль")
    def role_display(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.get_role_display() if profile else "—"

    @admin.display(description="Аккаунт")
    def account_display(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.account if profile and profile.account else "—"

    @admin.action(description="Войти от имени выбранного пользователя")
    def impersonate_user(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Выберите ровно одного пользователя.", messages.ERROR)
            return

        target = queryset.first()
        if target.is_superuser:
            self.message_user(request, "Нельзя войти от имени суперпользователя.", messages.ERROR)
            return

        request.session["_impersonate_user_id"] = target.pk
        security_logger.warning(
            "impersonate_start: superuser %s (%s) → user %s (%s)",
            request.user.pk,
            request.user.username,
            target.pk,
            target.username,
        )
        self.message_user(
            request,
            f"Вы работаете от имени {target.get_full_name() or target.username}.",
            messages.SUCCESS,
        )
        return redirect("trips:list")


# Перерегистрация стандартной модели User
try:
    admin.site.unregister(User)
except NotRegistered:
    pass

admin.site.register(User, UserAdmin)
