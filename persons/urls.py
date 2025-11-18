from django.urls import path

from . import views

app_name = 'persons'

urlpatterns = [
    path('create/', views.PersonCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', views.PersonUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.PersonDeleteView.as_view(), name='delete'),
    path('', views.PersonListView.as_view(), name='list'),
]
