from django.urls import path

from .views import (
    AccountCabinetView,
    AccountUserCreateView,
    AccountUserPasswordResetView,
    AccountUserRoleUpdateView,
    AccountUserUpdateView,
    RegisterView,
    SwitchOrganizationView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("switch-org/", SwitchOrganizationView.as_view(), name="switch_org"),
    path("cabinet/", AccountCabinetView.as_view(), name="cabinet"),
    path("users/create/", AccountUserCreateView.as_view(), name="user_create"),
    path(
        "users/<int:profile_id>/update/",
        AccountUserUpdateView.as_view(),
        name="user_update",
    ),
    path(
        "users/<int:profile_id>/role/",
        AccountUserRoleUpdateView.as_view(),
        name="user_role_update",
    ),
    path(
        "users/<int:profile_id>/reset-password/",
        AccountUserPasswordResetView.as_view(),
        name="user_reset_password",
    ),
]
