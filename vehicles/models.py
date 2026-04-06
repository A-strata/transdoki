from django.db import models
from django.urls import reverse

from organizations.models import Organization
from transdoki.models import UserOwnedModel

VEHICLE_TYPE_LENTH = 100
GRN_LENTH = 20
BRAND_MODEL_LENGTH = 20
PROPERTY_TYPE_LENGTH = 10


class VehicleType(models.TextChoices):
    SINGLE = "single", "Грузовик одиночный"
    TRUCK = "truck", "Тягач седельный"
    TRAILER = "trailer", "Прицеп"


class PropertyType(models.TextChoices):
    PROPERTY = "property", "Собственность"
    COPROPERTY = "coproperty", "Совместная собственность супругов"
    RENT = "rent", "Аренда"
    LEASING = "leasing", "Лизинг"
    UNPAID = "unpaid", "Безвозмездное пользование"


class Vehicle(UserOwnedModel):
    """Машины и прицепы."""

    class Status(models.TextChoices):
        AT_PARK = "AT_PARK", "В парке"
        ON_LINE = "ON_LINE", "На линии"
        TRANSFER = "TRANSFER", "Пересмена"

    grn = models.CharField(max_length=GRN_LENTH, verbose_name="Регистрационный номер")
    brand = models.CharField(max_length=BRAND_MODEL_LENGTH, verbose_name="Марка")
    model = models.CharField(max_length=20, verbose_name="Модель", blank=True)
    vehicle_type = models.CharField(
        max_length=PROPERTY_TYPE_LENGTH,
        choices=VehicleType.choices,
        verbose_name="Тип ТС",
    )
    property_type = models.CharField(
        max_length=PROPERTY_TYPE_LENGTH,
        choices=PropertyType.choices,
        verbose_name="Тип владения",
        default=PropertyType.PROPERTY,
    )
    owner = models.ForeignKey(
        Organization, on_delete=models.PROTECT, verbose_name="Cобственник ТС", default=1
    )
    current_odometer = models.PositiveIntegerField("Текущий одометр", default=0)
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.AT_PARK,
    )

    def __str__(self):
        return f"{self.grn}, {self.brand}"

    def get_absolute_url(self):
        return reverse("vehicles:vehicle_list")

    class Meta:
        verbose_name = "Транспортное средство"
        verbose_name_plural = "Транспортные средства"
        constraints = [
            models.UniqueConstraint(
                fields=["account", "grn"], name="unique_grn_per_account"
            ),
        ]


class VehicleFueling(UserOwnedModel):
    """Факт заправки транспортного средства."""

    class Source(models.TextChoices):
        MANUAL = "manual", "Ручной ввод"
        FUEL_CARD = "fuel_card", "Топливная карта"

    class FuelType(models.TextChoices):
        DIESEL = "diesel", "ДТ"
        AI_92 = "ai_92", "АИ-92"
        AI_95 = "ai_95", "АИ-95"
        AI_98 = "ai_98", "АИ-98"
        CNG = "cng", "Метан (CNG)"
        LPG = "lpg", "Пропан (LPG)"
        ADBLUE = "adblue", "AdBlue"

    # ── Привязка ──
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name="fuelings",
        verbose_name="Транспортное средство",
    )
    waybill = models.ForeignKey(
        "waybills.Waybill",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fuelings",
        verbose_name="Путевой лист",
    )

    # ── Источник ──
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.MANUAL,
        verbose_name="Источник данных",
    )

    # ── Что и сколько ──
    fuel_type = models.CharField(
        max_length=10,
        choices=FuelType.choices,
        verbose_name="Тип топлива",
    )
    litres = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name="Объём (л)",
    )

    # ── Стоимость ──
    price_per_litre = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Цена за литр",
    )
    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Стоимость",
    )

    # ── Когда и где ──
    timestamp = models.DateTimeField(
        verbose_name="Дата и время заправки",
    )
    station_name = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="АЗС",
    )

    # ── Интеграция ──
    external_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
        verbose_name="Внешний ID транзакции",
    )
    raw_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Сырые данные API",
    )

    class Meta:
        verbose_name = "Заправка"
        verbose_name_plural = "Заправки"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["vehicle", "timestamp"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["vehicle", "source", "external_id"],
                condition=models.Q(external_id__gt=""),
                name="unique_fueling_external_id",
            ),
        ]

    def __str__(self):
        return (
            f"{self.get_fuel_type_display()} {self.litres}л"
            f" / {self.vehicle}"
            f" / {self.timestamp:%d.%m.%Y}"
        )
