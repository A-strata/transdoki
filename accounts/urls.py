from django.urls import path

from .views import AccountCabinetView, RegisterView

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("cabinet/", AccountCabinetView.as_view(), name="cabinet"),
]
