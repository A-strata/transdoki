from django.db import models

from transdoki.models import UserOwnedModel


class FuelCardTransaction(UserOwnedModel):
    """Транзакция по топливной карте (импорт из внешних систем)."""

    class Provider(models.TextChoices):
        PETROLPLUS = "petrolplus", "PetrolPlus"

    # ── Источник ──
    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        verbose_name="Провайдер",
    )
    external_id = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name="ID транзакции в системе провайдера",
    )

    # ── Карта и держатель ──
    card_number = models.CharField(
        max_length=50,
        verbose_name="Номер карты",
    )
    holder_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="Держатель карты",
    )

    # ── Топливо ──
    fuel_type = models.CharField(
        max_length=100,
        verbose_name="Тип топлива (оригинал из API)",
    )
    litres = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Объём (л)",
    )

    # ── Деньги ──
    price_per_litre = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name="Цена за литр",
    )
    total_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Сумма списания",
    )
    vat_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="НДС",
    )

    # ── Когда и где ──
    timestamp = models.DateTimeField(
        verbose_name="Дата и время операции",
    )
    station_name = models.CharField(
        max_length=300,
        blank=True,
        default="",
        verbose_name="АЗС",
    )

    # ── Организация-владелец договора ──
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="fuel_card_transactions",
        verbose_name="Организация (договор)",
    )

    # ── Сырые данные ──
    raw_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Сырые данные API",
    )

    class Meta:
        verbose_name = "Транзакция по топливной карте"
        verbose_name_plural = "Транзакции по топливным картам"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["organization", "timestamp"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "provider", "external_id"],
                name="unique_fuel_card_transaction",
            ),
        ]

    def __str__(self):
        return (
            f"{self.fuel_type} {self.litres}л"
            f" / карта {self.card_number}"
            f" / {self.timestamp:%d.%m.%Y}"
        )
