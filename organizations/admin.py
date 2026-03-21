# organizations/admin.py
from django.contrib import admin

from .models import Bank, Organization, OrganizationBank


class OrganizationBankInline(admin.TabularInline):
    model = OrganizationBank
    extra = 1


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "short_name",
        "inn",
        "is_own_company",
        "created_by",
        "petrolplus_integration_enabled",
    )
    list_filter = ("is_own_company", "petrolplus_integration_enabled", "created_by")
    search_fields = ("short_name", "full_name", "inn")
    inlines = [OrganizationBankInline]
    readonly_fields = ("petrolplus_credentials_updated_at",)


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ("bic", "bank_name", "corr_account")
    search_fields = ("bank_name", "bic")


@admin.register(OrganizationBank)
class OrganizationBankAdmin(admin.ModelAdmin):
    list_display = ("account_num", "account_owner", "account_bank")
    search_fields = ("account_num", "account_owner__short_name")
