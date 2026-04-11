"""
Перевод client_vat_rate и carrier_vat_rate
из CharField (TextChoices "20","10","7","5","0","")
в IntegerField (IntegerChoices 0,5,7,10,22 + NULL = Без НДС).

3-шаговая миграция:
  1. Добавить временные IntegerField
  2. Конвертировать данные (маппинг строка → int, raise при неизвестных)
  3. Удалить старые CharField, переименовать новые
"""

from django.db import migrations, models


# Маппинг: старый TextChoices → новый IntegerChoices
# "20" → 22 (ставка обновлена законодательством)
VAT_MAP = {
    "20": 22,
    "10": 10,
    "7": 7,
    "5": 5,
    "0": 0,
    "": None,   # пустая строка → NULL (Без НДС / не указано)
}


def convert_vat_forward(apps, schema_editor):
    Trip = apps.get_model("trips", "Trip")
    for trip in Trip.objects.all().only(
        "pk",
        "client_vat_rate", "carrier_vat_rate",
        "client_vat_rate_new", "carrier_vat_rate_new",
    ):
        for old_field, new_field in [
            ("client_vat_rate", "client_vat_rate_new"),
            ("carrier_vat_rate", "carrier_vat_rate_new"),
        ]:
            old_val = getattr(trip, old_field)
            if old_val not in VAT_MAP:
                raise ValueError(
                    f"Trip pk={trip.pk}: неизвестное значение "
                    f"{old_field}={old_val!r}. "
                    f"Допустимые: {list(VAT_MAP.keys())}"
                )
            setattr(trip, new_field, VAT_MAP[old_val])
        trip.save(update_fields=["client_vat_rate_new", "carrier_vat_rate_new"])


def convert_vat_backward(apps, schema_editor):
    REVERSE_MAP = {v: k for k, v in VAT_MAP.items()}
    Trip = apps.get_model("trips", "Trip")
    for trip in Trip.objects.all().only(
        "pk",
        "client_vat_rate", "carrier_vat_rate",
        "client_vat_rate_new", "carrier_vat_rate_new",
    ):
        for new_field, old_field in [
            ("client_vat_rate_new", "client_vat_rate"),
            ("carrier_vat_rate_new", "carrier_vat_rate"),
        ]:
            new_val = getattr(trip, new_field)
            setattr(trip, old_field, REVERSE_MAP.get(new_val, ""))
        trip.save(update_fields=["client_vat_rate", "carrier_vat_rate"])


class Migration(migrations.Migration):

    dependencies = [
        ("trips", "0043_trip_updated_by_tripattachment_updated_by"),
    ]

    operations = [
        # Шаг 1: добавить временные IntegerField
        migrations.AddField(
            model_name="trip",
            name="client_vat_rate_new",
            field=models.IntegerField(
                blank=True,
                null=True,
                verbose_name="Ставка НДС (заказчик)",
            ),
        ),
        migrations.AddField(
            model_name="trip",
            name="carrier_vat_rate_new",
            field=models.IntegerField(
                blank=True,
                null=True,
                verbose_name="Ставка НДС (перевозчик)",
            ),
        ),
        # Шаг 2: конвертировать данные
        migrations.RunPython(
            convert_vat_forward,
            convert_vat_backward,
        ),
        # Шаг 3: удалить старые, переименовать новые
        migrations.RemoveField(
            model_name="trip",
            name="client_vat_rate",
        ),
        migrations.RemoveField(
            model_name="trip",
            name="carrier_vat_rate",
        ),
        migrations.RenameField(
            model_name="trip",
            old_name="client_vat_rate_new",
            new_name="client_vat_rate",
        ),
        migrations.RenameField(
            model_name="trip",
            old_name="carrier_vat_rate_new",
            new_name="carrier_vat_rate",
        ),
    ]
