from django.contrib import admin
from django.core.exceptions import PermissionDenied

from transdoki.tenancy import get_request_account

from .models import Act, Invoice, InvoiceLine


def _get_request_account(request):
    try:
        return get_request_account(request)
    except PermissionDenied:
        return None


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    readonly_fields = ("amount_net", "vat_amount", "amount_total", "discount_amount")
    fields = (
        "trip", "kind", "description", "quantity", "unit", "unit_price",
        "discount_pct", "discount_amount", "vat_rate",
        "amount_net", "vat_amount", "amount_total",
    )

    def save_model(self, request, obj, form, change):
        obj.compute(last_edited="pct")
        super().save_model(request, obj, form, change)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "date", "customer", "status", "account", "created_by")
    list_filter = ("status", "date", "account")
    search_fields = ("number", "customer__short_name")
    readonly_fields = ("created_by", "updated_by", "created_at", "updated_at")
    inlines = [InvoiceLineInline]

    fieldsets = (
        (None, {"fields": ("number", "date", "payment_due", "customer", "status", "account")}),
        ("Служебные", {"fields": ("created_by", "updated_by", "created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        account = _get_request_account(request)
        if not account:
            return qs.none()
        return qs.filter(account=account)

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        if change:
            obj.updated_by = request.user
        if not obj.account_id:
            account = _get_request_account(request)
            if account:
                obj.account = account
        super().save_model(request, obj, form, change)


@admin.register(Act)
class ActAdmin(admin.ModelAdmin):
    list_display = ("number", "date", "status", "amount_total", "account", "created_by")
    list_filter = ("status", "date", "account")
    search_fields = ("number",)
    readonly_fields = (
        "amount_net", "vat_amount", "amount_total",
        "created_by", "updated_by", "created_at", "updated_at",
    )

    fieldsets = (
        (None, {"fields": ("number", "date", "status", "invoice", "description", "account")}),
        ("Суммы", {"fields": ("amount_net", "vat_amount", "amount_total")}),
        ("Служебные", {"fields": ("created_by", "updated_by", "created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        account = _get_request_account(request)
        if not account:
            return qs.none()
        return qs.filter(account=account)

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        if change:
            obj.updated_by = request.user
        if not obj.account_id:
            account = _get_request_account(request)
            if account:
                obj.account = account
        super().save_model(request, obj, form, change)
