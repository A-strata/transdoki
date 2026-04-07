from django.contrib import admin

from organizations.models import Organization
from transdoki.tenancy import get_request_account

from .models import Contract, ContractAttachment, ContractTemplate


def _get_account(request):
    try:
        return get_request_account(request)
    except Exception:
        return None


class ContractAttachmentInline(admin.TabularInline):
    model = ContractAttachment
    extra = 0
    readonly_fields = ("created_by", "updated_by", "created_at", "updated_at")


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "contract_type",
        "status",
        "own_company",
        "contractor",
        "date_signed",
        "valid_until",
        "amount",
        "account",
    )
    list_filter = ("status", "contract_type", "account")
    search_fields = ("number", "own_company__short_name", "contractor__short_name")
    readonly_fields = ("created_by", "updated_by", "created_at", "updated_at")
    inlines = [ContractAttachmentInline]

    fieldsets = (
        (
            "Основное",
            {
                "fields": (
                    "number",
                    "contract_type",
                    "status",
                    "date_signed",
                    "valid_until",
                    "amount",
                    "account",
                )
            },
        ),
        (
            "Стороны",
            {"fields": ("own_company", "contractor")},
        ),
        (
            "Содержание",
            {"fields": ("subject", "notes")},
        ),
        (
            "Аудит",
            {"fields": ("created_by", "updated_by", "created_at", "updated_at")},
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        account = _get_account(request)
        if not account:
            return qs.none()
        return qs.filter(account=account)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        account = _get_account(request)
        if not request.user.is_superuser and account:
            if db_field.name in ("own_company", "contractor"):
                kwargs["queryset"] = Organization.objects.filter(account=account)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        if change:
            obj.updated_by = request.user
        if not obj.account_id:
            account = _get_account(request)
            if account:
                obj.account = account
        super().save_model(request, obj, form, change)


@admin.register(ContractTemplate)
class ContractTemplateAdmin(admin.ModelAdmin):
    list_display = ("template_type", "account", "uploaded_at", "uploaded_by")
    list_filter = ("template_type", "account")
