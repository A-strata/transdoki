"""
Пересоздание модели Payment: FK на Organization вместо Invoice.
Старая таблица удаляется (содержала только тестовые данные).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_alter_usersession_last_activity"),
        ("invoicing", "0003_payment"),
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(name="Payment"),
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("date", models.DateField(verbose_name="Дата платежа")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="Сумма")),
                ("payment_method", models.CharField(
                    choices=[("cash", "Наличные"), ("bank_transfer", "Безналичный перевод")],
                    max_length=20,
                    verbose_name="Способ оплаты",
                )),
                ("description", models.CharField(blank=True, default="", max_length=255, verbose_name="Комментарий")),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="accounts.account")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="payments",
                    to="organizations.organization",
                    verbose_name="Контрагент",
                )),
            ],
            options={
                "verbose_name": "Платёж",
                "verbose_name_plural": "Платежи",
                "ordering": ["-date", "-pk"],
            },
        ),
    ]
