from django.urls import path

from . import views

app_name = 'vehicles'

urlpatterns = [
    path('create/', views.VehicleCreateView.as_view(), name='create'),
    path('', views.VehicleListView.as_view(), name='list'),
]