from django.urls import path

from . import views

app_name = "invoicing"

urlpatterns = [
    path("invoices/", views.InvoiceListView.as_view(), name="invoice_list"),
    path("invoices/create/", views.invoice_create, name="invoice_create"),
    path("invoices/<int:pk>/", views.InvoiceDetailView.as_view(), name="invoice_detail"),
    path("invoices/<int:pk>/edit/", views.InvoiceEditView.as_view(), name="invoice_edit"),
    path("invoices/<int:pk>/cancel/", views.InvoiceCancelView.as_view(), name="invoice_cancel"),
    path("invoices/<int:pk>/acts/create/", views.ActCreateView.as_view(), name="act_create"),
    path("acts/<int:pk>/", views.ActDetailView.as_view(), name="act_detail"),
]
