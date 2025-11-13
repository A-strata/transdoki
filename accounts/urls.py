from django.urls import path

from .views import RegisterView

# from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
]
