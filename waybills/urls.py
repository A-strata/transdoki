from django.urls import path

from .views import WaybillCreateView

app_name = 'waybills'

urlpatterns = [
    path('create/', WaybillCreateView.as_view(), name='create'),
]