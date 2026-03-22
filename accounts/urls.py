from django.urls import path

from .views import AccountCabinetView, AccountUserCreateView, RegisterView

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("cabinet/", AccountCabinetView.as_view(), name="cabinet"),
    path("users/create/", AccountUserCreateView.as_view(), name="user_create"),
]
