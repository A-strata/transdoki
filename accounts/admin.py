from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import UserProfile, UserSession


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Бизнес-профиль"
    extra = 0
    fields = ("account", "role")  # скрываем legacy-лимиты из User admin


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


try:
    admin.site.unregister(User)
except NotRegistered:
    pass

admin.site.register(User, UserAdmin)
