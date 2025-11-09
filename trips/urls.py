from django.urls import path
from . import views

app_name = 'trips'

urlpatterns = [
    path('create/', views.TripCreateView.as_view(), name='create'),
    path('', views.TripListView.as_view(), name='list'),
]