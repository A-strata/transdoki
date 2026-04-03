from django.urls import path

from .views import (
    WaybillCreateView,
    WaybillDetailView,
    WaybillFormV2View,
    WaybillListView,
    WaybillUpdateView,
)

app_name = "waybills"

urlpatterns = [
    path("", WaybillListView.as_view(), name="waybill-list"),
    path("create/", WaybillCreateView.as_view(), name="waybill-create"),
    path("v2/", WaybillFormV2View.as_view(), name="waybill-form-v2"),
    path("<int:pk>/", WaybillDetailView.as_view(), name="waybill-detail"),
    path("<int:pk>/edit/", WaybillUpdateView.as_view(), name="waybill-update"),
]
