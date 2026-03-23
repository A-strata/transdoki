from django.db import models


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
