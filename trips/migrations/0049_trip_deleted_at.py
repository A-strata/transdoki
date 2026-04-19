from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trips", "0048_backfill_internal_trip_carrier_cost"),
    ]

    operations = [
        migrations.AddField(
            model_name="trip",
            name="deleted_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="Soft-delete: запись остаётся в БД для правил биллинга (24ч).",
                null=True,
                verbose_name="Удалён",
            ),
        ),
    ]
