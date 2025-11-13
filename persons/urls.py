from django.urls import path

from . import views

app_name = 'persons'

urlpatterns = [
    path('create/', views.PersonCreateView.as_view(), name='create'),
    path('', views.PersonListView.as_view(), name='list'),
]
