from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Account, UserProfile, UserSession


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """Управление аккаунтами и их лимитами."""

    list_display = (
        "name",
        "owner",
        "max_sessions",
        "max_own_companies",
        "is_active",
        "created_at",
    )
    list_editable = ("max_sessions", "max_own_companies", "is_active")
    search_fields = ("name", "owner__username", "owner__email")
    list_filter = ("is_active",)
    raw_id_fields = ("owner",)  # Удобно, если пользователей очень много


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Бизнес-профиль"
    extra = 0
    # Выводим account и role для редактирования,
    # а лимиты аккаунта — только для информации (readonly)
    fields = ("account", "role", "get_max_sessions", "get_max_companies")
    readonly_fields = ("get_max_sessions", "get_max_companies")

    @admin.display(description="Лимит сессий (из Аккаунта)")
    def get_max_sessions(self, obj):
        return obj.account.max_sessions if obj.account else "—"

    @admin.display(description="Лимит компаний (из Аккаунта)")
    def get_max_companies(self, obj):
        return obj.account.max_own_companies if obj.account else "—"


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

    @admin.display(description="Роль")
    def role_display(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.get_role_display() if profile else "—"

    @admin.display(description="Аккаунт")
    def account_display(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.account if profile and profile.account else "—"


# Перерегистрация стандартной модели User
try:
    admin.site.unregister(User)
except NotRegistered:
    pass

admin.site.register(User, UserAdmin)
