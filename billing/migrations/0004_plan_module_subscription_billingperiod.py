from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0011_userprofile_last_active_org"),
        ("billing", "0003_accountmodule"),
    ]

    operations = [
        migrations.CreateModel(
            name="Plan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=32, unique=True, verbose_name="Код")),
                ("name", models.CharField(max_length=128, verbose_name="Название")),
                (
                    "monthly_price",
                    models.DecimalField(
                        decimal_places=2, max_digits=10, verbose_name="Цена в месяц (₽)"
                    ),
                ),
                (
                    "trip_limit",
                    models.IntegerField(
                        blank=True,
                        help_text="NULL = без ограничений",
                        null=True,
                        verbose_name="Лимит рейсов в месяц",
                    ),
                ),
                (
                    "user_limit",
                    models.IntegerField(
                        blank=True,
                        help_text="NULL = без ограничений",
                        null=True,
                        verbose_name="Лимит пользователей",
                    ),
                ),
                (
                    "organization_limit",
                    models.IntegerField(
                        blank=True,
                        help_text="NULL = без ограничений. Считаются только is_own_company=True.",
                        null=True,
                        verbose_name="Лимит своих организаций",
                    ),
                ),
                (
                    "overage_price",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=10,
                        null=True,
                        verbose_name="Цена за рейс сверх лимита (₽)",
                    ),
                ),
                (
                    "is_custom",
                    models.BooleanField(
                        default=False,
                        help_text="True для Corporate. Параметры подписки переопределяются в Subscription.custom_*.",
                        verbose_name="Индивидуальный",
                    ),
                ),
                ("display_order", models.IntegerField(default=0, verbose_name="Порядок отображения")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен в выборе")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлён")),
            ],
            options={
                "verbose_name": "Тарифный план",
                "verbose_name_plural": "Тарифные планы",
                "ordering": ["display_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="Module",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=32, unique=True, verbose_name="Код")),
                ("name", models.CharField(max_length=128, verbose_name="Название")),
                (
                    "monthly_price",
                    models.DecimalField(
                        decimal_places=2, max_digits=10, verbose_name="Цена в месяц (₽)"
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен в каталоге")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
            ],
            options={
                "verbose_name": "Модуль",
                "verbose_name_plural": "Модули",
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "billing_cycle",
                    models.CharField(
                        choices=[("monthly", "Ежемесячно"), ("yearly", "Ежегодно")],
                        default="monthly",
                        max_length=16,
                        verbose_name="Периодичность",
                    ),
                ),
                (
                    "custom_monthly_price",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=10, null=True,
                        verbose_name="Индивидуальная цена (₽/мес)",
                    ),
                ),
                (
                    "custom_trip_limit",
                    models.IntegerField(blank=True, null=True, verbose_name="Индивидуальный лимит рейсов"),
                ),
                (
                    "custom_user_limit",
                    models.IntegerField(blank=True, null=True, verbose_name="Индивидуальный лимит пользователей"),
                ),
                (
                    "custom_organization_limit",
                    models.IntegerField(blank=True, null=True, verbose_name="Индивидуальный лимит организаций"),
                ),
                (
                    "custom_overage_price",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=10, null=True,
                        verbose_name="Индивидуальная цена overage (₽/рейс)",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Активна"),
                            ("past_due", "Просрочка"),
                            ("suspended", "Приостановлена"),
                            ("cancelled", "Отменена"),
                        ],
                        db_index=True,
                        default="active",
                        max_length=16,
                        verbose_name="Статус",
                    ),
                ),
                ("started_at", models.DateTimeField(verbose_name="Дата начала подписки")),
                ("current_period_start", models.DateTimeField(verbose_name="Начало текущего периода")),
                ("current_period_end", models.DateTimeField(verbose_name="Конец текущего периода")),
                ("past_due_since", models.DateTimeField(blank=True, null=True, verbose_name="В past_due с")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создана")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлена")),
                (
                    "account",
                    models.OneToOneField(
                        on_delete=models.deletion.CASCADE,
                        related_name="subscription",
                        to="accounts.account",
                        verbose_name="Аккаунт",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="billing.plan",
                        verbose_name="Тариф",
                    ),
                ),
                (
                    "scheduled_plan",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="+",
                        to="billing.plan",
                        verbose_name="Отложенный план (даунгрейд)",
                    ),
                ),
            ],
            options={
                "verbose_name": "Подписка",
                "verbose_name_plural": "Подписки",
            },
        ),
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(fields=["current_period_end"], name="billing_sub_current_c59a21_idx"),
        ),
        migrations.CreateModel(
            name="BillingPeriod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("period_start", models.DateField(verbose_name="Начало периода")),
                ("period_end", models.DateField(verbose_name="Конец периода")),
                ("plan_code", models.CharField(max_length=32, verbose_name="Код тарифа на момент расчёта")),
                ("confirmed_trips", models.IntegerField(verbose_name="Подтверждённых рейсов")),
                (
                    "trip_limit",
                    models.IntegerField(
                        blank=True, null=True,
                        help_text="NULL для Corporate с безлимитом",
                        verbose_name="Лимит рейсов",
                    ),
                ),
                ("overage_trips", models.IntegerField(default=0, verbose_name="Рейсов сверх лимита")),
                (
                    "subscription_fee",
                    models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Цена подписки (₽)"),
                ),
                (
                    "modules_fee",
                    models.DecimalField(
                        decimal_places=2, default=Decimal("0"), max_digits=10,
                        verbose_name="Цена модулей (₽)",
                    ),
                ),
                (
                    "overage_fee",
                    models.DecimalField(
                        decimal_places=2, default=Decimal("0"), max_digits=10,
                        verbose_name="Плата за overage (₽)",
                    ),
                ),
                ("total", models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Итого (₽)")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Черновик"),
                            ("invoiced", "Выставлен"),
                            ("paid", "Оплачен"),
                            ("written_off", "Списан"),
                        ],
                        default="draft",
                        max_length=16,
                        verbose_name="Статус",
                    ),
                ),
                ("charged_at", models.DateTimeField(blank=True, null=True, verbose_name="Списано")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                (
                    "modules_snapshot",
                    models.JSONField(blank=True, default=list, verbose_name="Снимок модулей"),
                ),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="billing_periods",
                        to="accounts.account",
                        verbose_name="Аккаунт",
                    ),
                ),
            ],
            options={
                "verbose_name": "Расчётный период",
                "verbose_name_plural": "Расчётные периоды",
            },
        ),
        migrations.AddConstraint(
            model_name="billingperiod",
            constraint=models.UniqueConstraint(
                fields=("account", "period_start"),
                name="billing_period_unique_account_start",
            ),
        ),
        migrations.AddIndex(
            model_name="billingperiod",
            index=models.Index(fields=["account", "-period_start"], name="billing_bil_account_2c8927_idx"),
        ),
        migrations.AddIndex(
            model_name="billingperiod",
            index=models.Index(fields=["status"], name="billing_bil_status_4159f3_idx"),
        ),
    ]
