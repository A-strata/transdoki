from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.urls import include, path
from django.views import View


class HomeView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect("trips:list")
        return redirect("billing:pricing")


urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(next_page="login"),
        name="logout",
    ),
    path("", include("billing.urls")),
    path("organizations/", include("organizations.urls")),
    path("persons/", include("persons.urls")),
    path("vehicles/", include("vehicles.urls")),
    path("trips/", include("trips.urls")),
    path("waybills/", include("waybills.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
