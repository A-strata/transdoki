from django.urls import path

from .views import (
    VehicleCreateStandaloneView,
    VehicleCreateView,
    VehicleDeleteView,
    VehicleDetailView,
    VehicleListView,
    VehicleSearchView,
    VehicleUpdateView,
    vehicle_quick_create,
)

app_name = 'vehicles'

urlpatterns = [
    path('create/', VehicleCreateStandaloneView.as_view(), name='create'),
    path(
        'create/<int:organization_pk>/',
        VehicleCreateView.as_view(),
        name='create_for_org',
    ),
    path('<int:pk>/', VehicleDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', VehicleUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', VehicleDeleteView.as_view(), name='delete'),
    path(
        '',
        VehicleListView.as_view(),
        name='list'
    ),
    path('quick-create/', vehicle_quick_create, name='quick_create'),
    path('search/', VehicleSearchView.as_view(), name='search'),
]
