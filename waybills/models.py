from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.timezone import localdate

from organizations.models import Organization, UserOwnedModel
from persons.models import Person
from vehicles.models import Vehicle


class Waybill(UserOwnedModel):
    # Порядковый номер путевого листа в пределах года.
    # Заполняется автоматически в service-слое.

    class Status(models.TextChoices):
        OPEN = "OPEN", "Открыт"
        CLOSED = "CLOSED", "Закрыт"

    number = models.PositiveIntegerField(
        verbose_name="Номер",
        editable=False,
        help_text="Генерируется автоматически в пределах года",
    )
    # Дата документа.
    date = models.DateField(
        verbose_name="Дата",
        default=localdate,
    )
    # Год храним отдельно для нумерации и ограничения уникальности.
    year = models.PositiveIntegerField(
        verbose_name="Год",
        editable=False,
        db_index=True,
    )
    # Организация, к которой относится путевой лист.
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="waybills",
        verbose_name="Организация",
    )
    driver = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name="waybills",
        verbose_name="Водитель",
    )
    # Основной автомобиль.
    truck = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name="waybills_of_truck",
        verbose_name="Автомобиль",
    )

    # Прицеп, если используется.
    trailer = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name="waybills_of_trailer",
        verbose_name="Прицеп",
        blank=True,
        null=True,
    )
    status = models.CharField(
        "Статус",
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
    )
    opened_at = models.DateTimeField("Открыт", default=timezone.now)
    closed_at = models.DateTimeField("Закрыт", null=True, blank=True)

    def clean(self):
        # Всегда синхронизируем year с date.
        if self.date:
            self.year = self.date.year

        # Автомобиль и прицеп не должны совпадать.
        if self.trailer and self.truck_id == self.trailer_id:
            raise ValidationError(
                {"trailer": "Автомобиль и прицеп не могут совпадать."}
            )

        # После создания запрещаем менять дату,
        # чтобы не ломать годовую нумерацию.
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).only("date").first()
            if original and original.date != self.date:
                raise ValidationError(
                    {"date": ("Нельзя изменять дату после создания путевого листа.")}
                )

    def save(self, *args, **kwargs):
        # Технически поддерживаем year в актуальном состоянии.
        if self.date:
            self.year = self.date.year
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"ПЛ №{self.number} от {self.date}"

    class Meta:
        verbose_name = "Путевой лист"
        verbose_name_plural = "Путевые листы"
        ordering = ["-date", "-number"]
        constraints = [
            # Номер не должен повторяться у пользователя в пределах года.
            models.UniqueConstraint(
                fields=["created_by", "year", "number"],
                name="unique_waybill_number_per_user_per_year",
            ),
        ]


class WaybillEvent(models.Model):
    """Отвечает за эксплуатационное состояние ТС и сменную логику"""

    class Type(models.TextChoices):
        OUT = "OUT", "Выпуск на линию"
        GIVE = "GIVE", "Сдача ТС"
        TAKE = "TAKE", "Прием ТС"
        RETURN = "RETURN", "Возвращение с линии"

    waybill = models.ForeignKey(
        Waybill,
        related_name="events",
        on_delete=models.CASCADE,
        verbose_name="Путевой лист",
    )
    event_type = models.CharField("Операция", max_length=10, choices=Type.choices)
    timestamp = models.DateTimeField("Время", default=timezone.now, db_index=True)
    odometer = models.PositiveIntegerField("Одометр")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp", "id"]
        indexes = [
            models.Index(fields=["waybill", "timestamp"]),
            models.Index(fields=["timestamp"]),
        ]

    def clean(self):
        if self.waybill_id and self.odometer < 0:
            raise ValidationError("Пробег не может быть отрицательным")

    def __str__(self):
        return (
            f"{self.get_event_type_display()} / {{self.waybill}} / {{self.timestamp}}"
        )


class RoutePoint(models.Model):
    class Type(models.TextChoices):
        LOAD = "LOAD", "Погрузка"
        UNLOAD = "UNLOAD", "Выгрузка"

    waybill = models.ForeignKey(
        Waybill,
        on_delete=models.CASCADE,
        related_name="route_points",
        verbose_name="Путевой лист",
    )
    point_type = models.CharField("Тип точки", max_length=10, choices=Type.choices)
    sequence = models.PositiveSmallIntegerField("Порядок")
    timestamp = models.DateTimeField("Время", default=timezone.now, db_index=True)
    address = models.CharField("Адрес", max_length=500, blank=True)
    odometer = models.PositiveIntegerField("Одометр")

    class Meta:
        ordering = ["timestamp", "id"]
        indexes = [
            models.Index(fields=["waybill", "timestamp"]),
            models.Index(fields=["point_type", "timestamp"]),
            models.Index(fields=["waybill", "sequence"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["waybill", "sequence"],
                name="uniq_route_point_sequence_per_waybill",
            ),
        ]

    def __str__(self):
        return (
            f"{self.get_point_type_display()} / "
            f"{self.waybill.number} / #{self.sequence}"
        )
