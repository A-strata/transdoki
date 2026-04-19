import uuid
from decimal import Decimal

from django.db import models


class Plan(models.Model):
    """
    Тарифный план подписки.

    Лимиты (trip_limit, user_limit, organization_limit) — null означает
    «без ограничений» и используется для Corporate.

    is_custom=True для Corporate-плана: параметры подписки конкретного
    аккаунта переопределяются через Subscription.custom_*.
    """

    CODE_FREE = "free"
    CODE_START = "start"
    CODE_BUSINESS = "business"
    CODE_CORPORATE = "corporate"

    code = models.CharField(max_length=32, unique=True, verbose_name="Код")
    name = models.CharField(max_length=128, verbose_name="Название")
    monthly_price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Цена в месяц (₽)"
    )
    trip_limit = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Лимит рейсов в месяц",
        help_text="NULL = без ограничений",
    )
    user_limit = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Лимит пользователей",
        help_text="NULL = без ограничений",
    )
    organization_limit = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Лимит своих организаций",
        help_text="NULL = без ограничений. Считаются только is_own_company=True.",
    )
    overage_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Цена за рейс сверх лимита (₽)",
    )
    is_custom = models.BooleanField(
        default=False,
        verbose_name="Индивидуальный",
        help_text="True для Corporate. Параметры подписки переопределяются в Subscription.custom_*.",
    )
    display_order = models.IntegerField(default=0, verbose_name="Порядок отображения")
    is_active = models.BooleanField(default=True, verbose_name="Активен в выборе")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлён")

    class Meta:
        verbose_name = "Тарифный план"
        verbose_name_plural = "Тарифные планы"
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Module(models.Model):
    """
    Платный модуль, подключаемый к аккаунту поверх тарифа.

    Модуль — отдельная ежемесячная подписка, доступная на любом тарифе.
    Код модуля используется во всём коде (account_has_module, ModuleRequiredMixin).
    """

    code = models.CharField(max_length=32, unique=True, verbose_name="Код")
    name = models.CharField(max_length=128, verbose_name="Название")
    monthly_price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Цена в месяц (₽)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен в каталоге")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    class Meta:
        verbose_name = "Модуль"
        verbose_name_plural = "Модули"
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Subscription(models.Model):
    """
    Подписка аккаунта на тариф.

    Один аккаунт — одна подписка (OneToOne). При регистрации назначается free.
    current_period_start..current_period_end — текущий оплачиваемый месяц.
    scheduled_plan — отложенный даунгрейд, применяется на следующем биллинге.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Активна"
        PAST_DUE = "past_due", "Просрочка"
        SUSPENDED = "suspended", "Приостановлена"
        CANCELLED = "cancelled", "Отменена"

    class BillingCycle(models.TextChoices):
        MONTHLY = "monthly", "Ежемесячно"
        YEARLY = "yearly", "Ежегодно"

    account = models.OneToOneField(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="subscription",
        verbose_name="Аккаунт",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        verbose_name="Тариф",
    )
    billing_cycle = models.CharField(
        max_length=16,
        choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY,
        verbose_name="Периодичность",
    )

    # Индивидуальные параметры (для Corporate). null = брать из плана.
    custom_monthly_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Индивидуальная цена (₽/мес)",
    )
    custom_trip_limit = models.IntegerField(
        null=True, blank=True, verbose_name="Индивидуальный лимит рейсов"
    )
    custom_user_limit = models.IntegerField(
        null=True, blank=True, verbose_name="Индивидуальный лимит пользователей"
    )
    custom_organization_limit = models.IntegerField(
        null=True, blank=True, verbose_name="Индивидуальный лимит организаций"
    )
    custom_overage_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Индивидуальная цена overage (₽/рейс)",
    )

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
        verbose_name="Статус",
    )
    started_at = models.DateTimeField(verbose_name="Дата начала подписки")
    current_period_start = models.DateTimeField(verbose_name="Начало текущего периода")
    current_period_end = models.DateTimeField(verbose_name="Конец текущего периода")
    past_due_since = models.DateTimeField(
        null=True, blank=True, verbose_name="В past_due с"
    )

    scheduled_plan = models.ForeignKey(
        Plan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Отложенный план (даунгрейд)",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлена")

    class Meta:
        verbose_name = "Подписка"
        verbose_name_plural = "Подписки"
        indexes = [
            models.Index(fields=["current_period_end"]),
        ]

    def __str__(self):
        return f"{self.account} → {self.plan.code}"

    @property
    def effective_monthly_price(self) -> Decimal:
        if self.custom_monthly_price is not None:
            return self.custom_monthly_price
        return self.plan.monthly_price

    @property
    def effective_trip_limit(self) -> int | None:
        if self.custom_trip_limit is not None:
            return self.custom_trip_limit
        return self.plan.trip_limit

    @property
    def effective_user_limit(self) -> int | None:
        if self.custom_user_limit is not None:
            return self.custom_user_limit
        return self.plan.user_limit

    @property
    def effective_organization_limit(self) -> int | None:
        if self.custom_organization_limit is not None:
            return self.custom_organization_limit
        return self.plan.organization_limit

    @property
    def effective_overage_price(self) -> Decimal | None:
        if self.custom_overage_price is not None:
            return self.custom_overage_price
        return self.plan.overage_price


class PaymentOrder(models.Model):
    """
    Намерение пополнить баланс через CloudPayments.

    Жизненный цикл:
      pending  →  paid      (webhook Pay пришёл, деньги зачислены)
      pending  →  failed    (webhook Fail или истёк срок)
      paid/failed → нельзя вернуть назад (финальные статусы)

    Поле order_id (UUID) передаётся в CloudPayments-виджет как InvoiceId.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает оплаты"
        PAID = "paid", "Оплачен"
        FAILED = "failed", "Ошибка / отменён"

    order_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name="ID заказа",
        help_text="Передаётся в CloudPayments как InvoiceId",
    )
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.PROTECT,
        related_name="payment_orders",
        verbose_name="Аккаунт",
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Сумма (₽)"
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="Статус",
    )
    cp_transaction_id = models.BigIntegerField(
        null=True, blank=True, verbose_name="ID транзакции CloudPayments"
    )
    cp_data = models.JSONField(default=dict, blank=True, verbose_name="Данные CloudPayments")
    transaction = models.OneToOneField(
        "BillingTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_order",
        verbose_name="Транзакция биллинга",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Создан")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Завершён")

    class Meta:
        verbose_name = "Платёжный заказ"
        verbose_name_plural = "Платёжные заказы"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Заказ {self.order_id} — {self.amount}₽ [{self.get_status_display()}]"


class BillingPeriod(models.Model):
    """
    Расчётный период подписки — один месяц.

    Создаётся в charge_monthly по факту закрытия периода. Unique-ключ
    (account, period_start) обеспечивает идемпотентность повторных запусков.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        INVOICED = "invoiced", "Выставлен"
        PAID = "paid", "Оплачен"
        WRITTEN_OFF = "written_off", "Списан"

    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="billing_periods",
        verbose_name="Аккаунт",
    )
    period_start = models.DateField(verbose_name="Начало периода")
    period_end = models.DateField(verbose_name="Конец периода")

    plan_code = models.CharField(max_length=32, verbose_name="Код тарифа на момент расчёта")
    confirmed_trips = models.IntegerField(verbose_name="Подтверждённых рейсов")
    trip_limit = models.IntegerField(
        null=True, blank=True, verbose_name="Лимит рейсов",
        help_text="NULL для Corporate с безлимитом",
    )
    overage_trips = models.IntegerField(default=0, verbose_name="Рейсов сверх лимита")

    subscription_fee = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Цена подписки (₽)"
    )
    modules_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"), verbose_name="Цена модулей (₽)"
    )
    overage_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"), verbose_name="Плата за overage (₽)"
    )
    total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Итого (₽)")

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Статус",
    )
    charged_at = models.DateTimeField(null=True, blank=True, verbose_name="Списано")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    # Снимок активных модулей: [{"code": ..., "price": "..."}, ...]
    # Историческое значение, не используется для расчёта.
    modules_snapshot = models.JSONField(
        default=list, blank=True, verbose_name="Снимок модулей"
    )

    class Meta:
        verbose_name = "Расчётный период"
        verbose_name_plural = "Расчётные периоды"
        constraints = [
            models.UniqueConstraint(
                fields=["account", "period_start"],
                name="billing_period_unique_account_start",
            ),
        ]
        indexes = [
            models.Index(fields=["account", "-period_start"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.account} {self.period_start}..{self.period_end} [{self.total}₽]"


class BillingTransaction(models.Model):
    """
    Запись об изменении баланса аккаунта.

    Расширена из старой модели: старые kind = deposit / charge сохранены для
    обратной совместимости с PaymentOrder и legacy-данными. Новые kind
    (subscription, overage, module, upgrade, refund, adjustment) — для v2.

    amount хранится положительным по старой семантике (kind различает направление).
    balance_after — снимок баланса после операции, для аудита.
    """

    class Kind(models.TextChoices):
        # Старые kind — сохраняем для совместимости с существующими записями и PaymentOrder
        DEPOSIT = "deposit", "Пополнение"
        CHARGE = "charge", "Списание (legacy)"
        # Новые v2
        SUBSCRIPTION = "subscription", "Списание подписки"
        OVERAGE = "overage", "Списание overage"
        MODULE = "module", "Списание модуля"
        UPGRADE = "upgrade", "Доплата за апгрейд"
        REFUND = "refund", "Возврат"
        ADJUSTMENT = "adjustment", "Корректировка"

    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name="Аккаунт",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, verbose_name="Тип операции")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Сумма")
    balance_after = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Баланс после операции"
    )
    description = models.CharField(max_length=255, blank=True, default="", verbose_name="Описание")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Метаданные")
    billing_period = models.ForeignKey(
        BillingPeriod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
        verbose_name="Расчётный период",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Дата операции")

    class Meta:
        verbose_name = "Транзакция"
        verbose_name_plural = "Транзакции"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["account", "-created_at"]),
            models.Index(fields=["kind"]),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} {self.amount}₽ — {self.account}"


class AccountModule(models.Model):
    """
    Платный модуль, подключённый к аккаунту.

    v2: module стал FK на Module. Жизненный цикл модуля:
      - activate_module() — устанавливает is_active=True, ended_at=None
      - deactivate_module() — is_active=False, ended_at = конец текущего периода
      - charge_monthly списывает только за is_active=True
    """

    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="account_modules",
        verbose_name="Аккаунт",
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.PROTECT,
        related_name="activations",
        verbose_name="Модуль",
    )
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Подключён")
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name="Отключён")
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Активен")

    class Meta:
        verbose_name = "Модуль аккаунта"
        verbose_name_plural = "Модули аккаунтов"
        constraints = [
            models.UniqueConstraint(
                fields=["account", "module"],
                name="accountmodule_unique_account_module",
            ),
        ]

    def __str__(self):
        return f"{self.module.code} — {self.account}"
