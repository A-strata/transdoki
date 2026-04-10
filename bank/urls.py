from django.urls import path

from . import views

app_name = "bank"

urlpatterns = [
    path("", views.BankStatementView.as_view(), name="statement"),
    path("payments/create/", views.PaymentCreateView.as_view(), name="payment_create"),
    path("payments/<int:pk>/delete/", views.PaymentDeleteView.as_view(), name="payment_delete"),
]
