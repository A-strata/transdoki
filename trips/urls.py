from django.urls import path
from . import views

app_name = 'trips'

urlpatterns = [
    path('create/', views.TripCreateView.as_view(), name='create'),
    path('<int:pk>/print-tn/', views.print_tn, name='print_tn'),
    path('', views.TripListView.as_view(), name='list'),

]