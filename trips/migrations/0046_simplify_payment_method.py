"""
Упрощение PaymentMethod: три варианта → два.

cashless_vat    → cashless  (vat_rate берётся из поля client/carrier_vat_rate)
cashless_no_vat → cashless  (vat_rate = NULL → «Без НДС»)

Обратная миграция: cashless → cashless_no_vat (безопасный дефолт).
"""

from django.db import migrations, models


FORWARD_MAP = {
    "cashless_vat": "cashless",
    "cashless_no_vat": "cashless",
}

KNOWN_VALUES = {"cash", "cashless_vat", "cashless_no_vat", ""}


def convert_forward(apps, schema_editor):
    Trip = apps.get_model("trips", "Trip")
    for field_name in ("client_payment_method", "carrier_payment_method"):
        for trip in Trip.objects.exclude(**{field_name: ""}).exclude(**{field_name: "cash"}):
            old_val = getattr(trip, field_name)
            if old_val not in KNOWN_VALUES:
                raise ValueError(
                    f"Trip pk={trip.pk}: неизвестное значение "
                    f"{field_name}={old_val!r}. "
                    f"Допустимые: {sorted(KNOWN_VALUES)}"
                )
            new_val = FORWARD_MAP.get(old_val, old_val)
            if new_val != old_val:
                setattr(trip, field_name, new_val)
                trip.save(update_fields=[field_name])


def convert_backward(apps, schema_editor):
    Trip = apps.get_model("trips", "Trip")
    for trip in Trip.objects.filter(client_payment_method="cashless"):
        trip.client_payment_method = "cashless_no_vat"
        trip.save(update_fields=["client_payment_method"])
    for trip in Trip.objects.filter(carrier_payment_method="cashless"):
        trip.carrier_payment_method = "cashless_no_vat"
        trip.save(update_fields=["carrier_payment_method"])


class Migration(migrations.Migration):

    dependencies = [
        ("trips", "0045_alter_trip_carrier_vat_rate_and_more"),
    ]

    operations = [
        # Сначала конвертация данных (пока choices ещё старые)
        migrations.RunPython(
            convert_forward,
            convert_backward,
        ),
        # Затем обновление choices на полях
        migrations.AlterField(
            model_name="trip",
            name="client_payment_method",
            field=models.CharField(
                blank=True,
                choices=[("cash", "Наличными (в т.ч. на карту)"), ("cashless", "Безнал")],
                default="",
                max_length=20,
                verbose_name="Форма оплаты (заказчик)",
            ),
        ),
        migrations.AlterField(
            model_name="trip",
            name="carrier_payment_method",
            field=models.CharField(
                blank=True,
                choices=[("cash", "Наличными (в т.ч. на карту)"), ("cashless", "Безнал")],
                default="",
                max_length=20,
                verbose_name="Форма оплаты (перевозчик)",
            ),
        ),
    ]
