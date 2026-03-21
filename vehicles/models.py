from django.db import models
from django.urls import reverse

from organizations.models import Organization, UserOwnedModel

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
        Organization, on_delete=models.CASCADE, verbose_name="Cобственник ТС", default=1
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
                fields=["created_by", "grn"], name="unique_grn_per_user"
            ),
            models.UniqueConstraint(
                fields=["account", "grn"], name="unique_grn_per_account"
            ),
        ]
