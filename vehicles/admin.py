from django.contrib import admin
from django.core.exceptions import PermissionDenied

from organizations.models import Organization
from transdoki.tenancy import get_request_account

from .models import Vehicle


def _get_request_account(request):
    """
    Совместимость для admin:
    - используем общий tenancy helper
    - сохраняем прежнее поведение admin (если account не найден -> None)
    """
    try:
        return get_request_account(request)
    except PermissionDenied:
        return None


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        "grn",
        "brand",
        "model",
        "vehicle_type",
        "status",
        "owner",
        "account",
        "created_by",
    )
    list_filter = ("vehicle_type", "status", "property_type", "account")
    search_fields = ("grn", "brand", "model")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        account = _get_request_account(request)
        if not account:
            return qs.none()
        return qs.filter(account=account)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        account = _get_request_account(request)
        if not request.user.is_superuser and account and db_field.name == "owner":
            kwargs["queryset"] = Organization.objects.filter(account=account)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        if not obj.account_id:
            account = _get_request_account(request)
            if account:
                obj.account = account
        super().save_model(request, obj, form, change)
