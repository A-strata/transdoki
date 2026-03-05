from django.urls import path

from .views import (TripCreateView, TripDetailView, TripListView,
                    TripUpdateView, TripTNDownloadView,
                    TripAgreementDownloadView,
                    address_suggest)

app_name = 'trips'

urlpatterns = [
    path('create/', TripCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', TripUpdateView.as_view(), name='edit'),
    path('', TripListView.as_view(), name='list'),
    path('<int:pk>/', TripDetailView.as_view(), name='detail'),

    path("api/address-suggest/", address_suggest, name="address_suggest"),
    path(
        "<int:pk>/download-tn/",
        TripTNDownloadView.as_view(),
        name="download_tn"),
    path(
        "<int:pk>/download-agreement/",
        TripAgreementDownloadView.as_view(),
        name="download_agreement"),
]
