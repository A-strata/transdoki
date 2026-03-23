from django.urls import path

from .views import VehicleCreateView, VehicleListView, VehicleUpdateView, vehicle_quick_create, vehicle_search

app_name = 'vehicles'

urlpatterns = [
    path(
        'create/<int:organization_pk>/',
        VehicleCreateView.as_view(),
        name='create'
    ),
    path('<int:pk>/edit/', VehicleUpdateView.as_view(), name='edit'),
    path(
        '',
        VehicleListView.as_view(),
        name='list'
    ),
    path('quick-create/', vehicle_quick_create, name='quick_create'),
    path('search/', vehicle_search, name='search'),
]
