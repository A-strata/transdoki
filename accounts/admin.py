from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import UserProfile, UserSession


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Бизнес-профиль"


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = (
        "username",
        "email",
        "get_max_sessions",
        "get_max_companies",
        "is_staff",
    )

    @admin.display(description="Лимит сессий")
    def get_max_sessions(self, obj):
        return obj.profile.max_sessions

    @admin.display(description="Лимит компаний")
    def get_max_companies(self, obj):
        return obj.profile.max_own_companies


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "session_key", "last_activity", "is_active")
    list_filter = ("is_active", "user")
    search_fields = ("session_key", "user__username")


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
