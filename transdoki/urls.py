from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='login', permanent=False)),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('accounts/login/',
         auth_views.LoginView.as_view(template_name='registration/login.html'),
         name='login'
         ),
    path('accounts/logout/',
         auth_views.LogoutView.as_view(next_page='login'),
         name='logout'),
    path('organizations/', include('organizations.urls')),
    path('persons/', include('persons.urls')),
    path('vehicles/', include('vehicles.urls')),
    path('trips/', include('trips.urls')),
    path('waybills/', include('waybills.urls')),
]
