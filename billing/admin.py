from django.contrib import admin

from .models import BillingTransaction, PaymentOrder


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
