from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('accounts/login/', 
            auth_views.LoginView.as_view(template_name='registration/login.html'), 
            name='login'),
    path('accounts/logout/', 
         auth_views.LogoutView.as_view(next_page='login'), 
         name='logout'),
    path('organizations/', include('organizations.urls')),
    path('persons/', include('persons.urls')),
    path('vehicles/', include('vehicles.urls')),
    path('trips/', include('trips.urls')),
]
