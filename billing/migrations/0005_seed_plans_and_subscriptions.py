"""
Seed-миграция тарифов и Free-подписок.

1. Создаёт 4 плана (free, start, business, corporate) согласно ТЗ v2 §3.1.
2. Создаёт модуль `contracts` с ценой 0 ₽ (см. ТЗ: платность модуля —
   отдельное продуктовое решение; до этого — бесплатно).
3. Всем существующим аккаунтам (без учёта is_billing_exempt — подписка
   обязательна всем) создаёт Subscription на Free.

Идемпотентно: повторный запуск не дублирует записи.
"""
from datetime import timedelta
from decimal import Decimal

from django.db import migrations
from django.utils import timezone


PLANS = [
    {
        "code": "free",
        "name": "Free",
        "monthly_price": Decimal("0.00"),
        "trip_limit": 10,
        "user_limit": 2,
        "organization_limit": 1,
        "overage_price": None,
        "is_custom": False,
        "display_order": 1,
    },
    {
        "code": "start",
        "name": "Старт",
        "monthly_price": Decimal("1490.00"),
        "trip_limit": 80,
        "user_limit": 5,
        "organization_limit": 3,
        "overage_price": Decimal("22.00"),
        "is_custom": False,
        "display_order": 2,
    },
    {
        "code": "business",
        "name": "Бизнес",
        "monthly_price": Decimal("4490.00"),
        "trip_limit": 350,
        "user_limit": 15,
        "organization_limit": 10,
        "overage_price": Decimal("16.00"),
        "is_custom": False,
        "display_order": 3,
    },
    {
        "code": "corporate",
        "name": "Корпоративный",
        "monthly_price": Decimal("11990.00"),
        "trip_limit": 1200,
        "user_limit": None,
        "organization_limit": None,
        "overage_price": None,
        "is_custom": True,
        "display_order": 4,
    },
]


def _add_months(dt, months):
    """Минимальный аналог dateutil.relativedelta(months=+1) без внешней зависимости."""
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(
        dt.day,
        [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
         31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1],
    )
    return dt.replace(year=year, month=month, day=day)


def seed(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    Module = apps.get_model("billing", "Module")
    Account = apps.get_model("accounts", "Account")
    Subscription = apps.get_model("billing", "Subscription")

    for data in PLANS:
        Plan.objects.update_or_create(code=data["code"], defaults=data)

    Module.objects.update_or_create(
        code="contracts",
        defaults={
            "name": "Договоры",
            "monthly_price": Decimal("0.00"),
            "is_active": True,
        },
    )

    free_plan = Plan.objects.get(code="free")
    now = timezone.now()
    period_end = _add_months(now, 1)

    for account in Account.objects.all():
        Subscription.objects.get_or_create(
            account=account,
            defaults={
                "plan": free_plan,
                "billing_cycle": "monthly",
                "status": "active",
                "started_at": now,
                "current_period_start": now,
                "current_period_end": period_end,
            },
        )


def unseed(apps, schema_editor):
    Subscription = apps.get_model("billing", "Subscription")
    Plan = apps.get_model("billing", "Plan")
    Module = apps.get_model("billing", "Module")

    Subscription.objects.all().delete()
    Plan.objects.filter(code__in=[p["code"] for p in PLANS]).delete()
    Module.objects.filter(code="contracts").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0004_plan_module_subscription_billingperiod"),
    ]

    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
