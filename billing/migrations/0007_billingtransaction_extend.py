"""
Расширение BillingTransaction под v2:
- kind: новые choices (subscription, overage, module, upgrade, refund, adjustment).
- FK billing_period (nullable) → BillingPeriod.
- Индексы по (account, -created_at) и (kind).
- description становится blank=True (не все новые транзакции имеют описание).
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0006_accountmodule_rebuild"),
    ]

    operations = [
        migrations.AlterField(
            model_name="billingtransaction",
            name="kind",
            field=models.CharField(
                choices=[
                    ("deposit", "Пополнение"),
                    ("charge", "Списание (legacy)"),
                    ("subscription", "Списание подписки"),
                    ("overage", "Списание overage"),
                    ("module", "Списание модуля"),
                    ("upgrade", "Доплата за апгрейд"),
                    ("refund", "Возврат"),
                    ("adjustment", "Корректировка"),
                ],
                max_length=16,
                verbose_name="Тип операции",
            ),
        ),
        migrations.AlterField(
            model_name="billingtransaction",
            name="description",
            field=models.CharField(
                blank=True, default="", max_length=255, verbose_name="Описание"
            ),
        ),
        migrations.AddField(
            model_name="billingtransaction",
            name="billing_period",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="transactions",
                to="billing.billingperiod",
                verbose_name="Расчётный период",
            ),
        ),
        migrations.AddIndex(
            model_name="billingtransaction",
            index=models.Index(
                fields=["account", "-created_at"],
                name="billing_bil_account_c6ae9e_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="billingtransaction",
            index=models.Index(fields=["kind"], name="billing_bil_kind_03dd60_idx"),
        ),
    ]
