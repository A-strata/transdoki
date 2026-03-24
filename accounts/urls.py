from django.urls import path

from .views import (
    AccountCabinetView,
    AccountUserCreateView,
    AccountUserPasswordResetView,
    AccountUserRoleUpdateView,
    RegisterView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("cabinet/", AccountCabinetView.as_view(), name="cabinet"),
    path("users/create/", AccountUserCreateView.as_view(), name="user_create"),
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
