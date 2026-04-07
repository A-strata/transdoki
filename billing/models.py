import uuid

from django.db import models


class PaymentOrder(models.Model):
    """
    Намерение пополнить баланс через CloudPayments.

    Жизненный цикл:
      pending  →  paid      (webhook Pay пришёл, деньги зачислены)
      pending  →  failed    (webhook Fail или истёк срок)
      paid/failed → нельзя вернуть назад (финальные статусы)

    Поле order_id (UUID) передаётся в CloudPayments-виджет как InvoiceId.
    CloudPayments вернёт его в каждом webhook-уведомлении — так мы
    идентифицируем аккаунт без сессии пользователя.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает оплаты"
        PAID = "paid", "Оплачен"
        FAILED = "failed", "Ошибка / отменён"

    # UUID генерируется автоматически при создании объекта.
    # Именно он уходит в CloudPayments как InvoiceId.
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
        max_digits=10,
        decimal_places=2,
        verbose_name="Сумма (₽)",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="Статус",
    )
    # Заполняется из webhook'а CloudPayments после успешной оплаты.
    # Нужен для поддержки возвратов и сверки с выпиской CP.
    cp_transaction_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="ID транзакции CloudPayments",
    )
    # Хранит данные из webhook: маску карты, код авторизации и т.п.
    # Не используем отдельные поля — CloudPayments может добавлять новые
    # атрибуты в ответ, JSONField безопасно это принимает.
    cp_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Данные CloudPayments",
    )
    # BillingTransaction, созданная при зачислении.
    # NULL пока заказ не оплачен. Позволяет пройти от платежа до транзакции
    # и обратно без дополнительных запросов.
    transaction = models.OneToOneField(
        "BillingTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_order",
        verbose_name="Транзакция биллинга",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Создан",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Завершён",
        help_text="Дата оплаты или отказа",
    )

    class Meta:
        verbose_name = "Платёжный заказ"
        verbose_name_plural = "Платёжные заказы"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Заказ {self.order_id} — {self.amount}₽ [{self.get_status_display()}]"


class BillingTransaction(models.Model):
    class Kind(models.TextChoices):
        DEPOSIT = "deposit", "Пополнение"
        CHARGE = "charge", "Списание"

    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name="Аккаунт",
    )
    kind = models.CharField(
        max_length=10,
        choices=Kind.choices,
        verbose_name="Тип операции",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Сумма",
    )
    balance_after = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Баланс после операции",
    )
    description = models.CharField(
        max_length=255,
        verbose_name="Описание",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Метаданные",
        help_text="Разбивка списания по сущностям или данные платежа",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата операции",
        db_index=True,
    )

    class Meta:
        verbose_name = "Транзакция"
        verbose_name_plural = "Транзакции"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.amount}₽ — {self.account}"


class AccountModule(models.Model):
    """Платный модуль, подключённый к аккаунту."""

    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="modules",
        verbose_name="Аккаунт",
    )
    module = models.CharField(
        max_length=40,
        verbose_name="Код модуля",
        help_text="Код из AVAILABLE_MODULES в billing/constants.py",
    )
    enabled_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Кто подключил",
    )
    enabled_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата подключения",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Действует до",
        help_text="NULL = бессрочно",
    )

    class Meta:
        unique_together = [("account", "module")]
        verbose_name = "Модуль аккаунта"
        verbose_name_plural = "Модули аккаунтов"

    def __str__(self):
        from billing.constants import AVAILABLE_MODULES

        label = AVAILABLE_MODULES.get(self.module, self.module)
        return f"{label} — {self.account}"
