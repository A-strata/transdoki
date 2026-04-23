from django.urls import path

from .views import (
    TripAgreementDownloadView,
    TripAttachmentDeleteView,
    TripAttachmentDownloadView,
    TripAttachmentUploadView,
    TripCreateView,
    TripDetailView,
    TripListView,
    TripSearchView,
    TripTNDownloadView,
    TripUpdateView,
    address_suggest,
)

app_name = "trips"

urlpatterns = [
    path("create/", TripCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", TripUpdateView.as_view(), name="edit"),
    path("", TripListView.as_view(), name="list"),
    path("<int:pk>/", TripDetailView.as_view(), name="detail"),

    path("api/address-suggest/", address_suggest, name="address_suggest"),
    path("search/", TripSearchView.as_view(), name="search"),
    path("<int:pk>/download-tn/", TripTNDownloadView.as_view(), name="download_tn"),
    path(
        "<int:pk>/download-agreement/",
        TripAgreementDownloadView.as_view(),
        name="download_agreement",
    ),
    path(
        "<int:pk>/attachments/upload/",
        TripAttachmentUploadView.as_view(),
        name="attachment_upload",
    ),
    path(
        "<int:pk>/attachments/<int:attachment_pk>/download/",
        TripAttachmentDownloadView.as_view(),
        name="attachment_download",
    ),
    path(
        "<int:pk>/attachments/<int:attachment_pk>/delete/",
        TripAttachmentDeleteView.as_view(),
        name="attachment_delete",
    ),
]
