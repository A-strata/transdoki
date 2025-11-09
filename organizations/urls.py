# organizations/urls.py
from django.urls import path
from . import views
from .api import get_org_data

app_name = 'organizations'

urlpatterns = [
    path('', views.OrganizationListView.as_view(), name='list'),
    path('create/', views.OrganizationCreateView.as_view(), name='create'),
    #path('<int:pk>/', views.OrganizationDetailView.as_view(), name='detail'),
    #path('<int:pk>/edit/', views.OrganizationUpdateView.as_view(), name='edit'),
    #path('<int:pk>/delete/', views.OrganizationDeleteView.as_view(), name='delete'),

    path('api/suggestions_by_inn/', get_org_data, name='api_suggestions_by_inn'),
]