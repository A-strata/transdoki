"""
Полный рефакторинг invoicing: нумерация (year+number), снятие статусов,
отвязка Act от Invoice, переход discount_pct в @property, editable=False
на производных полях, unique constraints, валидаторы, индексы.

Данные invoice/act/invoiceline на dev дропаются полностью — функционал
свежий, в проде не использовался (подтверждено перед применением).
Payment остаётся без потери данных.
"""

from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def drop_invoice_data(apps, schema_editor):
    apps.get_model("invoicing", "Act").objects.all().delete()
    apps.get_model("invoicing", "InvoiceLine").objects.all().delete()
    apps.get_model("invoicing", "Invoice").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("invoicing", "0008_add_quantity_unit_to_invoiceline"),
        ("organizations", "0024_alter_organization_unique_inn_per_account_and_more"),
        ("trips", "0046_simplify_payment_method"),
    ]

    operations = [
        # ── Дроп данных ДО schema-операций ─────────────────────────────
        migrations.RunPython(drop_invoice_data, migrations.RunPython.noop),

        # ── Invoice ────────────────────────────────────────────────────
        migrations.RemoveField(model_name="invoice", name="status"),
        migrations.AddField(
            model_name="invoice",
            name="year",
            field=models.PositiveSmallIntegerField(default=2026, editable=False, verbose_name="Год"),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="invoice",
            name="number",
            field=models.PositiveIntegerField(default=0, verbose_name="Номер"),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name="invoice",
            options={
                "ordering": ["-year", "-number"],
                "verbose_name": "Счёт",
                "verbose_name_plural": "Счета",
            },
        ),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(
                fields=("account", "year", "number"),
                name="uniq_invoice_account_year_number",
            ),
        ),

        # ── InvoiceLine ────────────────────────────────────────────────
        migrations.RemoveField(model_name="invoiceline", name="discount_pct"),
        migrations.AlterField(
            model_name="invoiceline",
            name="kind",
            field=models.CharField(
                choices=[("service", "Услуга"), ("penalty", "Штраф")],
                default="service",
                max_length=20,
                verbose_name="Тип",
            ),
        ),
        migrations.AlterField(
            model_name="invoiceline",
            name="quantity",
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal("1"),
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(Decimal("0.001"))],
                verbose_name="Количество",
            ),
        ),
        migrations.AlterField(
            model_name="invoiceline",
            name="unit_price",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                verbose_name="Цена без НДС",
            ),
        ),
        migrations.AlterField(
            model_name="invoiceline",
            name="discount_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                verbose_name="Скидка ₽",
            ),
        ),
        migrations.AlterField(
            model_name="invoiceline",
            name="amount_net",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0"), editable=False,
                max_digits=12, verbose_name="Сумма без НДС",
            ),
        ),
        migrations.AlterField(
            model_name="invoiceline",
            name="vat_amount",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0"), editable=False,
                max_digits=12, verbose_name="Сумма НДС",
            ),
        ),
        migrations.AlterField(
            model_name="invoiceline",
            name="amount_total",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0"), editable=False,
                max_digits=12, verbose_name="Сумма с НДС",
            ),
        ),
        migrations.AlterField(
            model_name="invoiceline",
            name="trip",
            field=models.ForeignKey(
                blank=True, db_index=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="invoice_lines",
                to="trips.trip",
                verbose_name="Рейс",
            ),
        ),

        # ── Act: отвязка от Invoice, свой customer, year+number ────────
        migrations.RemoveField(model_name="act", name="invoice"),
        migrations.RemoveField(model_name="act", name="status"),
        migrations.AddField(
            model_name="act",
            name="year",
            field=models.PositiveSmallIntegerField(default=2026, editable=False, verbose_name="Год"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="act",
            name="customer",
            field=models.ForeignKey(
                default=0,  # таблица пуста, значение не применяется
                on_delete=django.db.models.deletion.PROTECT,
                related_name="acts",
                to="organizations.organization",
                verbose_name="Заказчик",
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="act",
            name="number",
            field=models.PositiveIntegerField(default=0, verbose_name="Номер"),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="act",
            name="amount_net",
            field=models.DecimalField(
                decimal_places=2, max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                verbose_name="Сумма без НДС",
            ),
        ),
        migrations.AlterField(
            model_name="act",
            name="vat_amount",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0"), max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                verbose_name="Сумма НДС",
            ),
        ),
        migrations.AlterField(
            model_name="act",
            name="amount_total",
            field=models.DecimalField(
                decimal_places=2, max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                verbose_name="Сумма с НДС",
            ),
        ),
        migrations.AlterModelOptions(
            name="act",
            options={
                "ordering": ["-year", "-number"],
                "verbose_name": "Акт",
                "verbose_name_plural": "Акты",
            },
        ),
        migrations.AddConstraint(
            model_name="act",
            constraint=models.UniqueConstraint(
                fields=("account", "year", "number"),
                name="uniq_act_account_year_number",
            ),
        ),

        # ── Payment: валидатор на amount + композитный индекс ──────────
        migrations.AlterField(
            model_name="payment",
            name="amount",
            field=models.DecimalField(
                decimal_places=2, max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
                verbose_name="Сумма",
            ),
        ),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(
                fields=["account", "organization", "date"],
                name="idx_payment_acct_org_date",
            ),
        ),
    ]
