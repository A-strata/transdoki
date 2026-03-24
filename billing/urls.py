from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("billing/", views.TransactionListView.as_view(), name="transactions"),
    path("pricing/", views.PricingView.as_view(), name="pricing"),
]
