from django.urls import path

from .api import get_org_data, suggest_party
from .views import (
    OrganizationCreateView,
    OrganizationDeleteView,
    OrganizationDetailView,
    OrganizationListView,
    OrganizationUpdateView,
    OwnCompanyListView,
    organization_quick_create,
    organization_search,
)

app_name = "organizations"

urlpatterns = [
    path("", OrganizationListView.as_view(), name="list"),
    path("own/", OwnCompanyListView.as_view(), name="own_list"),
    path("create/", OrganizationCreateView.as_view(), name="create"),
    path("<int:pk>/", OrganizationDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", OrganizationUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", OrganizationDeleteView.as_view(), name="delete"),
    path("api/suggestions_by_inn/", get_org_data, name="api_suggestions_by_inn"),
    path("api/party_suggest/", suggest_party, name="api_party_suggest"),
    path("quick-create/", organization_quick_create, name="quick_create"),
    path("search/", organization_search, name="search"),
]
