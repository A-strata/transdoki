from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum

from transdoki.enums import VatRate
from transdoki.models import UserOwnedModel


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Наличные"
    BANK_TRANSFER = "bank_transfer", "Безналичный перевод"


class PaymentDirection(models.TextChoices):
    INCOMING = "incoming", "Поступление"
    OUTGOING = "outgoing", "Списание"


# ─────────────────────────────────────────────────────────────────────
# Invoice
# ─────────────────────────────────────────────────────────────────────


class Invoice(UserOwnedModel):
    year = models.PositiveSmallIntegerField(
        editable=False,
        verbose_name="Год",
    )
    number = models.PositiveIntegerField(verbose_name="Номер")
    date = models.DateField(verbose_name="Дата")
    payment_due = models.DateField(null=True, blank=True, verbose_name="Оплатить до")
    customer = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="invoices",
        verbose_name="Заказчик",
    )
    bank_account = models.ForeignKey(
        "organizations.OrganizationBank",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
        verbose_name="Банковский счёт",
    )

    class Meta:
        verbose_name = "Счёт"
        verbose_name_plural = "Счета"
        ordering = ["-year", "-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "year", "number"],
                name="uniq_invoice_account_year_number",
            ),
        ]

    def __str__(self):
        return f"{self.display_number} от {self.date}"

    @property
    def display_number(self) -> str:
        return f"СЧ-{self.year}-{self.number:04d}"

    def clean(self):
        if self.date and self.year and self.year != self.date.year:
            raise ValidationError(
                {
                    "date": "Год счёта зафиксирован при создании и не может "
                    "быть изменён. Для счёта в другом году создайте новый.",
                }
            )
        if self.payment_due and self.date and self.payment_due < self.date:
            raise ValidationError(
                {
                    "payment_due": "Срок оплаты не может быть раньше даты счёта.",
                }
            )
        # Tenant-check для bank_account выполняем только когда account
        # уже известен. При form.is_valid() ModelForm._post_clean вызывает
        # instance.full_clean() ДО того, как сервис успевает проставить
        # invoice.account — в этот момент self.account_id=None, и без
        # защиты ниже проверка даёт фолс-позитив на любом валидном банке.
        # Сервис вызывает full_clean() повторно после setattr(account),
        # и там уже проверка отрабатывает по-настоящему.
        if (
            self.account_id
            and self.bank_account_id
            and self.bank_account.account_id != self.account_id
        ):
            raise ValidationError(
                {
                    "bank_account": "Расчётный счёт не принадлежит вашей компании.",
                }
            )

    @property
    def total_net(self):
        return self.lines.aggregate(t=Sum("amount_net"))["t"] or Decimal("0")

    @property
    def total_vat(self):
        return self.lines.aggregate(t=Sum("vat_amount"))["t"] or Decimal("0")

    @property
    def total(self):
        return self.lines.aggregate(t=Sum("amount_total"))["t"] or Decimal("0")


# ─────────────────────────────────────────────────────────────────────
# InvoiceLine
# ─────────────────────────────────────────────────────────────────────


class InvoiceLine(models.Model):
    """
    Строка счёта.

    Не наследует UserOwnedModel — изоляция через invoice.account
    (осознанное решение). TenantManager недоступен, все запросы
    идут через invoice__account_id.
    """

    class Kind(models.TextChoices):
        SERVICE = "service", "Услуга"
        PENALTY = "penalty", "Штраф"

    class UnitOfMeasure(models.TextChoices):
        SERVICE = "усл.", "усл."  # ОКЕИ 642
        TRIP = "рейс", "рейс"  # ОКЕИ 796
        TON = "т", "т"  # ОКЕИ 168
        KM = "км", "км"  # ОКЕИ 008
        HOUR = "ч", "ч"  # ОКЕИ 356

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Счёт",
    )
    trip = models.ForeignKey(
        "trips.Trip",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invoice_lines",
        db_index=True,
        verbose_name="Рейс",
    )
    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
        default=Kind.SERVICE,
        verbose_name="Тип",
    )
    description = models.CharField(max_length=255, verbose_name="Наименование")

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0.001"))],
        verbose_name="Количество",
    )
    unit = models.CharField(
        max_length=10,
        choices=UnitOfMeasure.choices,
        default=UnitOfMeasure.SERVICE,
        verbose_name="Ед. изм.",
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Цена без НДС",
    )
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Скидка ₽",
    )
    vat_rate = models.IntegerField(
        choices=VatRate.choices,
        null=True,
        blank=True,
        verbose_name="Ставка НДС",
    )

    # Производные поля. editable=False → не попадают в ModelForm.
    amount_net = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        editable=False,
        verbose_name="Сумма без НДС",
    )
    vat_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        editable=False,
        verbose_name="Сумма НДС",
    )
    amount_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        editable=False,
        verbose_name="Сумма с НДС",
    )

    class Meta:
        verbose_name = "Строка счёта"
        verbose_name_plural = "Строки счёта"
        ordering = ["pk"]

    def __str__(self):
        return f"{self.description} — {self.amount_total} ₽"

    @property
    def discount_pct(self) -> Decimal:
        """Процент скидки как производное от discount_amount."""
        gross = (self.unit_price or Decimal("0")) * (self.quantity or Decimal("0"))
        if not gross:
            return Decimal("0")
        return (self.discount_amount / gross * 100).quantize(
            Decimal("0.01"),
            ROUND_HALF_UP,
        )

    def compute(self):
        """
        Пересчёт производных полей: amount_net, vat_amount, amount_total.

        Вызывается только из clean(). Прямой вызов запрещён контрактом.

        Идемпотентность: повторный вызов на том же объекте без изменения
        входных полей (unit_price, quantity, discount_amount, vat_rate)
        даёт тот же результат — compute() не читает собственные выходы.

        Это важно потому что валидация происходит дважды:
          1. InvoiceLineForm.clean() → instance.clean() — ради поимки
             ValidationError с привязкой к полю строки формсета
          2. services.create_invoice / update_invoice → line.full_clean() —
             на финальном объекте перед save()
        Оба вызова работают с одинаковыми входными данными, результат совпадает.
        """
        two = Decimal("0.01")

        unit_price = self.unit_price or Decimal("0")
        quantity = self.quantity or Decimal("0")
        discount = self.discount_amount or Decimal("0")

        gross = (unit_price * quantity).quantize(two, ROUND_HALF_UP)

        if discount > gross:
            raise ValidationError(
                {
                    "discount_amount": f"Скидка ({discount} ₽) не может превышать "
                    f"стоимость позиции ({gross} ₽).",
                }
            )

        self.amount_net = gross - discount

        if self.vat_rate is not None:
            self.vat_amount = (self.amount_net * self.vat_rate / 100).quantize(
                two, ROUND_HALF_UP
            )
        else:
            self.vat_amount = Decimal("0")

        self.amount_total = self.amount_net + self.vat_amount

    def clean(self):
        """
        Инварианты строки + пересчёт производных полей.

        Единственная точка входа в compute().
        """
        self.compute()

    # save() без логики. Контракт: перед save() всегда full_clean().


# ─────────────────────────────────────────────────────────────────────
# Act
# ─────────────────────────────────────────────────────────────────────


class Act(UserOwnedModel):
    """
    Акт — самостоятельный документ.

    Связь с Invoice будет добавлена в отдельной итерации. Сейчас акт
    создаётся и редактируется независимо, со своим контрагентом,
    описанием и суммами.
    """

    year = models.PositiveSmallIntegerField(
        editable=False,
        verbose_name="Год",
    )
    number = models.PositiveIntegerField(verbose_name="Номер")
    date = models.DateField(verbose_name="Дата")

    customer = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="acts",
        verbose_name="Заказчик",
    )
    description = models.TextField(verbose_name="Наименование услуги")

    amount_net = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Сумма без НДС",
    )
    vat_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Сумма НДС",
    )
    amount_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Сумма с НДС",
    )

    class Meta:
        verbose_name = "Акт"
        verbose_name_plural = "Акты"
        ordering = ["-year", "-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "year", "number"],
                name="uniq_act_account_year_number",
            ),
        ]

    def __str__(self):
        return f"{self.display_number} от {self.date}"

    @property
    def display_number(self) -> str:
        return f"АКТ-{self.year}-{self.number:04d}"

    def clean(self):
        if self.date and self.year and self.year != self.date.year:
            raise ValidationError(
                {
                    "date": "Год акта зафиксирован при создании и не может быть изменён.",
                }
            )
        # Инвариант сумм: total = net + vat.
        # Защита от ручного ввода несогласованных сумм через admin/shell.
        if (
            self.amount_net is not None
            and self.vat_amount is not None
            and self.amount_total is not None
        ):
            expected = self.amount_net + self.vat_amount
            if abs(self.amount_total - expected) > Decimal("0.01"):
                raise ValidationError(
                    {
                        "amount_total": f"Сумма с НДС ({self.amount_total}) должна равняться "
                        f"сумме без НДС + НДС ({expected}).",
                    }
                )


# ─────────────────────────────────────────────────────────────────────
# Payment
# ─────────────────────────────────────────────────────────────────────


class Payment(UserOwnedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name="Контрагент",
    )
    date = models.DateField(verbose_name="Дата платежа")
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Сумма",
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        verbose_name="Способ оплаты",
    )
    direction = models.CharField(
        max_length=20,
        choices=PaymentDirection.choices,
        default=PaymentDirection.INCOMING,
        verbose_name="Направление",
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Комментарий",
    )

    class Meta:
        verbose_name = "Платёж"
        verbose_name_plural = "Платежи"
        ordering = ["-date", "-pk"]
        indexes = [
            models.Index(
                fields=["account", "organization", "date"],
                name="idx_payment_acct_org_date",
            ),
        ]

    def __str__(self):
        return f"Платёж {self.amount} ₽ от {self.date}"
