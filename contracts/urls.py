from django.urls import path

from . import views

app_name = "contracts"

urlpatterns = [
    # Contract CRUD
    path("", views.ContractListView.as_view(), name="list"),
    path("create/", views.ContractCreateView.as_view(), name="create"),
    path("<int:pk>/", views.ContractDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.ContractUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.ContractDeleteView.as_view(), name="delete"),
    path("<int:pk>/download/", views.ContractDownloadView.as_view(), name="download"),
    # Attachments
    path(
        "<int:contract_pk>/attachments/create/",
        views.AttachmentCreateView.as_view(),
        name="attachment_create",
    ),
    path(
        "attachments/<int:pk>/download/",
        views.AttachmentDownloadView.as_view(),
        name="attachment_download",
    ),
    path(
        "attachments/<int:pk>/delete/",
        views.AttachmentDeleteView.as_view(),
        name="attachment_delete",
    ),
    # Template management
    path("templates/", views.TemplateSettingsView.as_view(), name="template_settings"),
    path(
        "templates/<str:template_type>/upload/",
        views.TemplateUploadView.as_view(),
        name="template_upload",
    ),
    path(
        "templates/<str:template_type>/delete/",
        views.TemplateDeleteView.as_view(),
        name="template_delete",
    ),
    path(
        "templates/<str:template_type>/download-default/",
        views.TemplateDownloadDefaultView.as_view(),
        name="template_download_default",
    ),
]
