from django.urls import path

from .views import TripCreateView, TripListView, TripUpdateView, TripDetailView, print_tn, address_suggest

app_name = 'trips'

urlpatterns = [
    path('create/', TripCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', TripUpdateView.as_view(), name='edit'),
    path('', TripListView.as_view(), name='list'),
    path('<int:pk>/', TripDetailView.as_view(), name='detail'),
    path('<int:pk>/print-tn/', print_tn, name='print_tn'),

    path("api/address-suggest/", address_suggest, name="address_suggest")
]
