from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.db.models import Sum

from transdoki.models import UserOwnedModel


class Invoice(UserOwnedModel):

    class Status(models.TextChoices):
        DRAFT     = "draft",     "Черновик"
        SENT      = "sent",      "Выставлен"
        PAID      = "paid",      "Оплачен"
        CANCELLED = "cancelled", "Аннулирован"

    number      = models.CharField(max_length=50, verbose_name="Номер")
    date        = models.DateField(verbose_name="Дата")
    payment_due = models.DateField(null=True, blank=True, verbose_name="Оплатить до")
    customer    = models.ForeignKey(
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
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
        verbose_name="Статус",
    )

    class Meta:
        verbose_name = "Счёт"
        verbose_name_plural = "Счета"
        ordering = ["-date", "-number"]

    def __str__(self):
        return f"{self.number} от {self.date}"

    @property
    def total_net(self):
        return self.lines.aggregate(t=Sum("amount_net"))["t"] or Decimal("0")

    @property
    def total_vat(self):
        return self.lines.aggregate(t=Sum("vat_amount"))["t"] or Decimal("0")

    @property
    def total(self):
        return self.lines.aggregate(t=Sum("amount_total"))["t"] or Decimal("0")


class InvoiceLine(models.Model):

    class Kind(models.TextChoices):
        SERVICE = "service", "Услуга"
        PENALTY = "penalty", "Штраф"

    class VatRate(models.IntegerChoices):
        ZERO   = 0,  "Без НДС"
        TEN    = 10, "10%"
        TWENTY = 20, "20%"

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
        verbose_name="Рейс",
    )
    kind        = models.CharField(max_length=20, choices=Kind.choices, verbose_name="Тип")
    description = models.CharField(max_length=255, verbose_name="Наименование")

    unit_price      = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена без НДС")
    discount_pct    = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"), verbose_name="Скидка %")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"), verbose_name="Скидка ₽")
    vat_rate        = models.IntegerField(choices=VatRate.choices, default=VatRate.ZERO, verbose_name="Ставка НДС")

    amount_net   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"), verbose_name="Сумма без НДС")
    vat_amount   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"), verbose_name="Сумма НДС")
    amount_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"), verbose_name="Сумма с НДС")

    class Meta:
        verbose_name = "Строка счёта"
        verbose_name_plural = "Строки счёта"
        ordering = ["pk"]

    def __str__(self):
        return f"{self.description} — {self.amount_total} ₽"

    def compute(self, *, last_edited: str = "amt") -> None:
        """
        Пересчёт сумм строки.

        last_edited="amt" (default) — discount_amount фиксирован, pct пересчитывается.
        last_edited="pct" — discount_pct фиксирован, amount пересчитывается.
            Используется только в apply_discount_to_invoice (массовая скидка).
        """
        two = Decimal("0.01")

        if not self.unit_price:
            self.discount_pct    = Decimal("0")
            self.discount_amount = Decimal("0")
            self.amount_net      = Decimal("0")
            self.vat_amount      = Decimal("0")
            self.amount_total    = Decimal("0")
            return

        if last_edited == "pct":
            if self.discount_pct > Decimal("99.99"):
                raise ValueError(
                    f"Скидка не может превышать 99.99% "
                    f"(указано {self.discount_pct}%)"
                )
            self.discount_amount = (
                self.unit_price * self.discount_pct / 100
            ).quantize(two, ROUND_HALF_UP)
        else:
            max_amt = self.unit_price - two
            if self.discount_amount > max_amt:
                raise ValueError(
                    f"Скидка ({self.discount_amount} ₽) не может быть "
                    f"больше {max_amt} ₽"
                )
            self.discount_pct = (
                self.discount_amount / self.unit_price * 100
            ).quantize(two, ROUND_HALF_UP)

        self.amount_net = (
            self.unit_price - self.discount_amount
        ).quantize(two, ROUND_HALF_UP)

        self.vat_amount = (
            self.amount_net * self.vat_rate / 100
        ).quantize(two, ROUND_HALF_UP)

        self.amount_total = (
            self.amount_net + self.vat_amount
        ).quantize(two, ROUND_HALF_UP)

    def save(self, *args, **kwargs):
        if not self.amount_net:
            self.compute()
        super().save(*args, **kwargs)


class Act(UserOwnedModel):

    class Status(models.TextChoices):
        DRAFT     = "draft",     "Черновик"
        SIGNED    = "signed",    "Подписан"
        CANCELLED = "cancelled", "Аннулирован"

    number  = models.CharField(max_length=50, verbose_name="Номер")
    date    = models.DateField(verbose_name="Дата")
    status  = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
        verbose_name="Статус",
    )
    invoice = models.OneToOneField(
        Invoice,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="act",
        verbose_name="Счёт",
    )
    description = models.TextField(verbose_name="Наименование услуги")

    amount_net   = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Сумма без НДС")
    vat_amount   = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Сумма НДС")
    amount_total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Сумма с НДС")

    class Meta:
        verbose_name = "Акт"
        verbose_name_plural = "Акты"
        ordering = ["-date", "-number"]

    def __str__(self):
        return f"Акт {self.number} от {self.date}"
