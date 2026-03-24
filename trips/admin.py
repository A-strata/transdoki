from django.contrib import admin
from django.core.exceptions import PermissionDenied

from organizations.models import Organization
from persons.models import Person
from transdoki.tenancy import get_request_account
from vehicles.models import Vehicle

from .models import Trip, TripAttachment


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


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = (
        "num_of_trip",
        "date_of_trip",
        "client",
        "driver",
        "truck",
        "client_cost",
        "carrier_cost",
        "account",
        "created_by",
    )
    list_filter = ("date_of_trip", "payment_type", "payment_condition", "account")
    search_fields = (
        "num_of_trip",
        "client__short_name",
        "driver__surname",
        "truck__grn",
    )
    readonly_fields = ("num_of_trip",)

    fieldsets = (
        (
            "Основная информация",
            {"fields": ("num_of_trip", "date_of_trip", "account", "created_by")},
        ),
        (
            "Участники",
            {
                "fields": (
                    ("client", "carrier"),
                    ("consignor", "consignee"),
                    ("driver", "truck", "trailer"),
                )
            },
        ),
        (
            "Груз",
            {
                "fields": (
                    ("cargo", "weight"),
                )
            },
        ),
        (
            "Финансы и оплата",
            {
                "fields": (
                    ("client_cost", "carrier_cost"),
                    ("payment_type", "payment_condition", "payment_term"),
                )
            },
        ),
    )

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
        if request.user.is_superuser or not account:
            return super().formfield_for_foreignkey(db_field, request, **kwargs)

        if db_field.name in ("client", "carrier", "consignor", "consignee"):
            kwargs["queryset"] = Organization.objects.filter(account=account)
        elif db_field.name == "driver":
            kwargs["queryset"] = Person.objects.filter(account=account)
        elif db_field.name in ("truck", "trailer"):
            kwargs["queryset"] = Vehicle.objects.filter(account=account)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        if not obj.account_id:
            account = _get_request_account(request)
            if account:
                obj.account = account
        super().save_model(request, obj, form, change)


@admin.register(TripAttachment)
class TripAttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "trip",
        "original_name",
        "file_size",
        "created_at",
        "account",
        "created_by",
    )
    search_fields = ("original_name", "trip__num_of_trip")
    list_filter = ("created_at", "account")

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
        if not request.user.is_superuser and account and db_field.name == "trip":
            kwargs["queryset"] = Trip.objects.filter(account=account)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        if not obj.account_id:
            account = _get_request_account(request)
            if account:
                obj.account = account
        super().save_model(request, obj, form, change)
