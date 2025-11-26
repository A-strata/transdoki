from django.urls import path

from .views import VehicleCreateView, VehicleListView, VehicleUpdateView

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
]
