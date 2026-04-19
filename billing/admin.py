from django.contrib import admin

from .models import (
    AccountModule,
    BillingPeriod,
    BillingTransaction,
    Module,
    PaymentOrder,
    Plan,
    Subscription,
)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "monthly_price",
        "trip_limit",
        "organization_limit",
        "user_limit",
        "overage_price",
        "is_custom",
        "is_active",
        "display_order",
    )
    list_filter = ("is_active", "is_custom")
    search_fields = ("code", "name")
    ordering = ("display_order", "id")


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "monthly_price", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "account",
        "plan",
        "status",
        "billing_cycle",
        "current_period_start",
        "current_period_end",
        "scheduled_plan",
    )
    list_filter = ("status", "plan", "billing_cycle")
    search_fields = ("account__name",)
    autocomplete_fields = ("account", "plan", "scheduled_plan")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("account", "plan", "billing_cycle", "status")}),
        ("Период", {"fields": ("started_at", "current_period_start", "current_period_end", "past_due_since")}),
        ("Отложенная смена", {"fields": ("scheduled_plan",)}),
        (
            "Индивидуальные параметры (для Corporate)",
            {
                "fields": (
                    "custom_monthly_price",
                    "custom_trip_limit",
                    "custom_user_limit",
                    "custom_organization_limit",
                    "custom_overage_price",
                ),
            },
        ),
        ("Метаданные", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(BillingPeriod)
class BillingPeriodAdmin(admin.ModelAdmin):
    list_display = (
        "account",
        "period_start",
        "period_end",
        "plan_code",
        "confirmed_trips",
        "overage_trips",
        "total",
        "status",
        "charged_at",
    )
    list_filter = ("status", "plan_code")
    search_fields = ("account__name",)
    readonly_fields = (
        "account",
        "period_start",
        "period_end",
        "plan_code",
        "confirmed_trips",
        "trip_limit",
        "overage_trips",
        "subscription_fee",
        "modules_fee",
        "overage_fee",
        "total",
        "modules_snapshot",
        "status",
        "charged_at",
        "created_at",
    )
    ordering = ("-period_start",)


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
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
    list_display = (
        "account",
        "kind",
        "amount",
        "balance_after",
        "billing_period",
        "description",
        "created_at",
    )
    list_filter = ("kind",)
    search_fields = ("account__name", "description")
    readonly_fields = (
        "account",
        "kind",
        "amount",
        "balance_after",
        "description",
        "metadata",
        "billing_period",
        "created_at",
    )
    ordering = ("-created_at",)


@admin.register(AccountModule)
class AccountModuleAdmin(admin.ModelAdmin):
    list_display = ("account", "module", "is_active", "started_at", "ended_at")
    list_filter = ("is_active", "module")
    search_fields = ("account__name", "module__code")
    autocomplete_fields = ("account", "module")
    readonly_fields = ("started_at",)
