from django.urls import path

from .api import get_org_data
from .views import (OrganizationCreateView, OrganizationDetailView,
                    OrganizationListView, OrganizationUpdateView)

app_name = 'organizations'

urlpatterns = [
    path('', OrganizationListView.as_view(), name='list'),
    path('create/', OrganizationCreateView.as_view(), name='create'),
    path('<int:pk>/', OrganizationDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', OrganizationUpdateView.as_view(), name='edit'),
    # path('<int:pk>/delete/',
    # views.OrganizationDeleteView.as_view(), name='delete'),

    path(
        'api/suggestions_by_inn/',
        get_org_data,
        name='api_suggestions_by_inn'
    ),
]
