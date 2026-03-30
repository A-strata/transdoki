from django.urls import path

from .api import get_org_data, suggest_bank, suggest_party
from .views import (
    OrganizationCreateView,
    OrganizationDeleteView,
    OrganizationDetailView,
    OrganizationListView,
    OrganizationUpdateView,
    OwnCompanyListView,
    bank_account_delete,
    bank_account_quick_create,
    bank_account_update,
    contact_delete,
    contact_quick_create,
    contact_update,
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
    path("api/bank_suggest/", suggest_bank, name="api_bank_suggest"),
    path("quick-create/", organization_quick_create, name="quick_create"),
    path("bank-account/quick-create/", bank_account_quick_create, name="bank_account_quick_create"),
    path("bank-account/update/", bank_account_update, name="bank_account_update"),
    path("bank-account/delete/", bank_account_delete, name="bank_account_delete"),
    path("contact/quick-create/", contact_quick_create, name="contact_quick_create"),
    path("contact/update/", contact_update, name="contact_update"),
    path("contact/delete/", contact_delete, name="contact_delete"),
    path("search/", organization_search, name="search"),
]
