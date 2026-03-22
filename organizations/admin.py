from django.contrib import admin
from django.core.exceptions import PermissionDenied

from transdoki.tenancy import get_request_account

from .models import Bank, Organization, OrganizationBank


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


class OrganizationBankInline(admin.TabularInline):
    model = OrganizationBank
    extra = 1


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "short_name",
        "inn",
        "is_own_company",
        "account",
        "created_by",
        "petrolplus_integration_enabled",
    )
    list_filter = ("is_own_company", "petrolplus_integration_enabled", "account")
    search_fields = ("short_name", "full_name", "inn")
    inlines = [OrganizationBankInline]
    readonly_fields = ("petrolplus_credentials_updated_at",)

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
        if not obj.account_id:
            account = _get_request_account(request)
            if account:
                obj.account = account
        super().save_model(request, obj, form, change)


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ("bic", "bank_name", "corr_account")
    search_fields = ("bank_name", "bic")


@admin.register(OrganizationBank)
class OrganizationBankAdmin(admin.ModelAdmin):
    list_display = (
        "account_num",
        "account_owner",
        "account_bank",
        "account",
        "created_by",
    )
    search_fields = ("account_num", "account_owner__short_name")
    list_filter = ("account",)

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
        if (
            not request.user.is_superuser
            and account
            and db_field.name == "account_owner"
        ):
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
