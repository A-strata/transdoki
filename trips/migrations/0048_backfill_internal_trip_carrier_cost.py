"""
Data-миграция: для старых внутрифирменных рейсов, где сумма лежала только
в client_cost (old-logic), зеркалим её в carrier_cost вместе с единицей
измерения и ставкой НДС. После этого perspective(carrier) возвращает
корректный income_total у перевозчика.

Критерий выборки:
    forwarder IS NULL
    client_cost IS NOT NULL
    carrier_cost IS NULL
    client.is_own_company = True
    carrier.is_own_company = True
    client_id != carrier_id

Копируем ровно три поля: carrier_cost, carrier_cost_unit, carrier_vat_rate.
carrier_payment_method НЕ копируем — платёжный метод на стороне перевозчика
может сознательно отличаться от платёжного метода клиента.

Обратима: reverse сбрасывает те же три поля в исходные значения для
записей, подходящих под тот же критерий (с carrier_cost, равным client_cost).
"""

from django.db import migrations
from django.db.models import F


def _eligible_qs(Trip):
    """Общий критерий выборки внутрифирменных рейсов без зеркалирования."""
    return (
        Trip.objects.filter(
            forwarder__isnull=True,
            client_cost__isnull=False,
            client__is_own_company=True,
            carrier__is_own_company=True,
        )
        .exclude(client_id=F("carrier_id"))
    )


def backfill_forward(apps, schema_editor):
    Trip = apps.get_model("trips", "Trip")
    qs = _eligible_qs(Trip).filter(carrier_cost__isnull=True)
    for trip in qs:
        trip.carrier_cost = trip.client_cost
        trip.carrier_cost_unit = trip.client_cost_unit
        trip.carrier_vat_rate = trip.client_vat_rate
        trip.save(
            update_fields=[
                "carrier_cost",
                "carrier_cost_unit",
                "carrier_vat_rate",
            ]
        )


def backfill_reverse(apps, schema_editor):
    """
    Обратная миграция: обнуляет carrier_cost/unit/vat_rate у внутрифирменных
    рейсов, где carrier_cost равен client_cost (признак того, что значение
    попало туда через forward-миграцию). Если кто-то после forward-миграции
    вручную поменял суммы — такая запись под критерий не попадёт и не будет
    тронута.
    """
    Trip = apps.get_model("trips", "Trip")
    qs = _eligible_qs(Trip).filter(carrier_cost=F("client_cost"))
    for trip in qs:
        trip.carrier_cost = None
        trip.carrier_cost_unit = ""
        trip.carrier_vat_rate = None
        trip.save(
            update_fields=[
                "carrier_cost",
                "carrier_cost_unit",
                "carrier_vat_rate",
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ("trips", "0047_trip_forwarder"),
        ("organizations", "0024_alter_organization_unique_inn_per_account_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_forward, backfill_reverse),
    ]
