from django.contrib import admin

from billing.constants import AVAILABLE_MODULES

from .models import AccountModule, BillingTransaction, PaymentOrder


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    # Колонки в списке заказов.
    # order_id (UUID) — для поиска по конкретному платежу.
    # cp_transaction_id — чтобы сверяться с выпиской CloudPayments.
    list_display = (
        "order_id",
        "account",
        "amount",
        "status",
        "cp_transaction_id",
        "created_at",
        "completed_at",
    )
    list_filter = ("status",)
    search_fields = ("order_id", "account__name", "cp_transaction_id")
    # Все поля только для чтения: финансовые данные нельзя редактировать вручную.
    # Изменение должно проходить только через сервисный слой.
    readonly_fields = (
        "order_id",
        "account",
        "amount",
        "status",
        "cp_transaction_id",
        "cp_data",
        "transaction",
        "created_at",
        "completed_at",
    )
    ordering = ("-created_at",)


@admin.register(BillingTransaction)
class BillingTransactionAdmin(admin.ModelAdmin):
    list_display = ("account", "kind", "amount", "balance_after", "description", "created_at")
    list_filter = ("kind",)
    search_fields = ("account__name", "description")
    readonly_fields = ("account", "kind", "amount", "balance_after", "description", "metadata", "created_at")
    ordering = ("-created_at",)


@admin.register(AccountModule)
class AccountModuleAdmin(admin.ModelAdmin):
    list_display = ("account", "module_display", "enabled_by", "enabled_at", "expires_at")
    list_filter = ("module",)
    search_fields = ("account__name",)
    readonly_fields = ("enabled_at",)
    autocomplete_fields = ("account",)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        choices = [("", "---------")] + [
            (code, label) for code, label in AVAILABLE_MODULES.items()
        ]
        form.base_fields["module"].widget = admin.widgets.AdminTextInputWidget()
        from django import forms as dj_forms

        form.base_fields["module"] = dj_forms.ChoiceField(
            choices=choices, label="Модуль"
        )
        return form

    def save_model(self, request, obj, form, change):
        if not obj.enabled_by_id:
            obj.enabled_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Модуль")
    def module_display(self, obj):
        return AVAILABLE_MODULES.get(obj.module, obj.module)
