from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("billing/", views.TransactionListView.as_view(), name="transactions"),
    path("billing/deposit/", views.DepositView.as_view(), name="deposit"),
    path("pricing/", views.PricingView.as_view(), name="pricing"),
    # CloudPayments webhook endpoints.
    # Эти URL регистрируются в личном кабинете CP (раздел "Уведомления")
    # после регистрации в сервисе. Сами view уже готовы к приёму запросов.
    path("billing/cloudpayments/check/", views.cloudpayments_check, name="cp_check"),
    path("billing/cloudpayments/pay/", views.cloudpayments_pay, name="cp_pay"),
    path("billing/cloudpayments/fail/", views.cloudpayments_fail, name="cp_fail"),
]
