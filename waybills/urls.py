from django.urls import path

from .views import (
    WaybillListView,
    WaybillCreateView,
    WaybillDetailView,
    WaybillUpdateView,
)

app_name = "waybills"

urlpatterns = [
    path("", WaybillListView.as_view(), name="waybill-list"),
    path("create/", WaybillCreateView.as_view(), name="waybill-create"),
    path("<int:pk>/", WaybillDetailView.as_view(), name="waybill-detail"),
    path("<int:pk>/edit/", WaybillUpdateView.as_view(), name="waybill-update"),
]