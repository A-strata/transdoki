import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import IntegrityError, models, transaction

from organizations.models import Organization
from transdoki.models import UserOwnedModel
from persons.models import Person
from persons.validators import validate_phone_number
from vehicles.models import Vehicle

from .validators import RussianMinValueValidator

CARGO_LENGTH = 20
LOADING_TYPE_LENGTH = 20
ADDRESS_LENGTH = 200


class LoadingType(models.TextChoices):
    REAR = "rear", "Задняя"
    TOP = "top", "Верхняя"
    SIDE = "side", "Боковая"


class PaymentCondition(models.TextChoices):
    DOCUMENTS = "documents", "По факту предоставления документов"
    UNLOADING = "unloading", "Оплата на выгрузке"


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Наличными (в т.ч. на карту)"
    CASHLESS_VAT = "cashless_vat", "Безнал с НДС"
    CASHLESS_NO_VAT = "cashless_no_vat", "Безнал без НДС"


class VatRate(models.TextChoices):
    VAT_20 = "20", "20%"
    VAT_10 = "10", "10%"
    VAT_7 = "7", "7%"
    VAT_5 = "5", "5%"
    VAT_0 = "0", "0%"


class CostUnit(models.TextChoices):
    RUB = "rub", "руб."
    RUB_PER_KM = "rub_km", "руб./км"
    RUB_PER_KG = "rub_kg", "руб./кг"
    RUB_PER_CBM = "rub_cbm", "руб./куб"
    RUB_PER_HOUR = "rub_hour", "руб./час"


class FinancialStatus(models.TextChoices):
    OPEN = "open", "Открыт"
    CALCULATED = "calculated", "Зафиксирован"
    INVOICED = "invoiced", "Документы выставлены"
    PAID = "paid", "Оплачен"


class Trip(UserOwnedModel):
    num_of_trip = models.PositiveSmallIntegerField(
        verbose_name="Номер заявки", editable=False
    )
    date_of_trip = models.DateField(verbose_name="Дата заявки")
    client = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="trips_as_client",
        verbose_name="Заказчик перевозки",
    )
    carrier = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="trips_as_carrier",
        verbose_name="Перевозчик",
    )
    driver = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name="trips_as_driver",
        verbose_name="Водитель",
    )
    truck = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name="trips_as_truck",
        verbose_name="Автомобиль",
    )
    trailer = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name="trips_as_trailer",
        verbose_name="Прицеп",
        blank=True,
        null=True,
    )
    cargo = models.CharField(max_length=CARGO_LENGTH, verbose_name="Груз")
    weight = models.PositiveIntegerField(verbose_name="Вес (кг)", blank=True, null=True)
    volume = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        verbose_name="Объём (м³)",
        blank=True,
        null=True,
        validators=[RussianMinValueValidator(0)],
    )
    client_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Ставка заказчику",
        blank=True,
        null=True,
        validators=[RussianMinValueValidator(0)],
    )
    client_cost_unit = models.CharField(
        max_length=20,
        choices=CostUnit.choices,
        default=CostUnit.RUB,
        blank=True,
        verbose_name="Единица измерения (заказчик)",
    )
    client_payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        blank=True,
        default="",
        verbose_name="Форма оплаты (заказчик)",
    )
    client_vat_rate = models.CharField(
        max_length=5,
        choices=VatRate.choices,
        blank=True,
        default="",
        verbose_name="Ставка НДС (заказчик)",
    )
    payment_condition = models.CharField(
        max_length=50,
        choices=PaymentCondition.choices,
        blank=True,
        default="",
        verbose_name="Условия оплаты (заказчик)",
    )
    payment_term = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Срок оплаты (заказчик, банк. дней)",
    )
    client_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        blank=True,
        null=True,
        verbose_name="Фактически (заказчик)",
        help_text="Фактический пробег (км) или время (ч) для расчёта итоговой суммы",
    )
    client_financial_status = models.CharField(
        max_length=20,
        choices=FinancialStatus.choices,
        default=FinancialStatus.OPEN,
        verbose_name="Статус расчётов (заказчик)",
    )
    client_total_fixed = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Итоговая сумма (заказчик, зафиксирована)",
    )
    carrier_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Ставка перевозчику",
        blank=True,
        null=True,
        validators=[RussianMinValueValidator(0)],
    )
    carrier_cost_unit = models.CharField(
        max_length=20,
        choices=CostUnit.choices,
        default=CostUnit.RUB,
        blank=True,
        verbose_name="Единица измерения (перевозчик)",
    )
    carrier_payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        blank=True,
        default="",
        verbose_name="Форма оплаты (перевозчик)",
    )
    carrier_vat_rate = models.CharField(
        max_length=5,
        choices=VatRate.choices,
        blank=True,
        default="",
        verbose_name="Ставка НДС (перевозчик)",
    )
    carrier_payment_condition = models.CharField(
        max_length=50,
        choices=PaymentCondition.choices,
        blank=True,
        default="",
        verbose_name="Условия оплаты (перевозчик)",
    )
    carrier_payment_term = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Срок оплаты (перевозчик, банк. дней)",
    )
    carrier_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        blank=True,
        null=True,
        verbose_name="Фактически (перевозчик)",
        help_text="Фактический пробег (км) или время (ч) для расчёта итоговой суммы",
    )
    carrier_financial_status = models.CharField(
        max_length=20,
        choices=FinancialStatus.choices,
        default=FinancialStatus.OPEN,
        verbose_name="Статус расчётов (перевозчик)",
    )
    carrier_total_fixed = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Итоговая сумма (перевозчик, зафиксирована)",
    )
    comments = models.TextField(
        max_length=1000,
        verbose_name="Комментарии",
        blank=True,
        help_text="Дополнительная информация о рейсе",
    )

    def _quantity_value(self, cost_unit, quantity_field):
        """Возвращает фактическое количество для расчёта исходя из единицы ставки."""
        if cost_unit == CostUnit.RUB_PER_KG:
            return Decimal(self.weight) if self.weight is not None else None
        if cost_unit == CostUnit.RUB_PER_CBM:
            return self.volume
        return quantity_field  # км или часы — хранятся отдельно

    def _compute_total(self, cost, cost_unit, quantity_field):
        qty = self._quantity_value(cost_unit, quantity_field)
        if cost_unit == CostUnit.RUB:
            return cost
        if cost and qty:
            return (cost * qty).quantize(Decimal("0.01"))
        return None

    @property
    def client_quantity_value(self):
        return self._quantity_value(self.client_cost_unit, self.client_quantity)

    @property
    def client_total(self):
        return self._compute_total(
            self.client_cost, self.client_cost_unit, self.client_quantity
        )

    @property
    def carrier_quantity_value(self):
        return self._quantity_value(self.carrier_cost_unit, self.carrier_quantity)

    @property
    def carrier_total(self):
        return self._compute_total(
            self.carrier_cost, self.carrier_cost_unit, self.carrier_quantity
        )

    @property
    def load_point(self):
        """Первая точка погрузки (sequence=1). Работает с prefetch_related('points')."""
        for p in self.points.all():
            if p.sequence == 1:
                return p
        return None

    @property
    def unload_point(self):
        """Точка выгрузки (sequence=2). Работает с prefetch_related('points')."""
        for p in self.points.all():
            if p.sequence == 2:
                return p
        return None

    def save(self, *args, **kwargs):
        # Для существующего рейса номер не пересчитываем
        if self.pk:
            return super().save(*args, **kwargs)

        # account обязателен: нумерация идёт отдельно для каждого аккаунта
        if not self.account_id:
            raise ValueError("account must be set before saving Trip")

        # Несколько попыток на случай гонки параллельных запросов
        for _ in range(5):
            try:
                # И вычисление номера, и save — в одной транзакции
                with transaction.atomic():
                    # Блокируем последнюю запись аккаунта до конца транзакции
                    last_trip = (
                        Trip.objects.select_for_update()
                        .filter(account_id=self.account_id)
                        .order_by("-num_of_trip")
                        .first()
                    )

                    # Если рейсы уже есть -> +1, иначе стартуем с 1
                    self.num_of_trip = (last_trip.num_of_trip + 1) if last_trip else 1

                    # Сохраняем внутри той же транзакции
                    return super().save(*args, **kwargs)

            except IntegrityError:
                # Если кто-то успел занять номер раньше — пробуем ещё раз
                continue

        # Если после нескольких попыток не вышло — отдаем ошибку выше
        raise IntegrityError("Не удалось сгенерировать уникальный номер рейса")

    class Meta:
        verbose_name = "Рейс"
        verbose_name_plural = "Рейсы"
        constraints = [
            models.UniqueConstraint(
                fields=["account", "num_of_trip", "date_of_trip"],
                name="unique_num_and_date_per_account",
            ),
        ]


class TripPoint(models.Model):
    """
    Точка маршрута рейса (погрузка или выгрузка груза).

    Заменяет плоские поля Trip (loading_address, unloading_address и т.д.)
    и позволяет хранить произвольное количество точек в хронологическом порядке.

    Поле waybill + odometer используются для расчёта реальных затрат рейса:
    по одометру на момент погрузки/выгрузки можно определить, какую долю
    километража каждого путевого листа занял данный рейс.
    """

    class Type(models.TextChoices):
        LOAD = "LOAD", "Погрузка"
        UNLOAD = "UNLOAD", "Выгрузка"

    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name="points",
        verbose_name="Рейс",
    )
    point_type = models.CharField(
        max_length=10,
        choices=Type.choices,
        verbose_name="Тип точки",
    )
    sequence = models.PositiveSmallIntegerField(
        verbose_name="Порядковый номер",
        help_text="Хронологический порядок точек внутри рейса",
    )

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="trip_points",
        verbose_name="Организация",
        null=True,
        blank=True,
        help_text="Грузоотправитель (для погрузки) или грузополучатель (для выгрузки)",
    )

    # Коммерческие данные (перенесены из плоских полей Trip)
    address = models.CharField(
        max_length=ADDRESS_LENGTH,
        verbose_name="Адрес",
    )
    planned_date = models.DateField(
        verbose_name="Заявленная дата",
    )
    planned_time = models.TimeField(
        verbose_name="Заявленное время",
        null=True,
        blank=True,
    )
    actual_date = models.DateField(
        verbose_name="Фактическая дата",
        null=True,
        blank=True,
    )
    actual_time = models.TimeField(
        verbose_name="Фактическое время",
        null=True,
        blank=True,
    )
    contact_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
        verbose_name="Контакт (имя)",
    )
    contact_phone = models.CharField(
        max_length=25,
        blank=True,
        default="",
        verbose_name="Контакт (телефон)",
        validators=[validate_phone_number],
    )
    loading_type = models.CharField(
        max_length=LOADING_TYPE_LENGTH,
        choices=LoadingType.choices,
        blank=True,
        default="",
        verbose_name="Тип погрузки/выгрузки",
    )

    # Данные для расчёта затрат — заполняются постфактум
    waybill = models.ForeignKey(
        "waybills.Waybill",
        on_delete=models.SET_NULL,
        related_name="trip_points",
        verbose_name="Путевой лист",
        null=True,
        blank=True,
    )
    odometer = models.PositiveIntegerField(
        verbose_name="Показание одометра",
        null=True,
        blank=True,
        help_text="Показание одометра путевого листа в момент погрузки/выгрузки",
    )

    class Meta:
        verbose_name = "Точка маршрута рейса"
        verbose_name_plural = "Точки маршрута рейса"
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["trip", "sequence"],
                name="unique_trippoint_sequence_per_trip",
            ),
        ]

    def __str__(self):
        return f"{self.get_point_type_display()} #{self.sequence} / {self.trip}"


ALLOWED_TRIP_FILE_EXTENSIONS = [
    "pdf",
    "jpg",
    "jpeg",
    "png",
    "doc",
    "docx",
    "xls",
    "xlsx",
]
MAX_TRIP_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
MAX_FILES_PER_TRIP = 10


def trip_attachment_upload_to(instance, filename):
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    unique_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    return f"trip_attachments/user_{instance.created_by_id}/trip_{instance.trip_id}/{unique_name}"


def validate_trip_file_size(file_obj):
    if file_obj.size > MAX_TRIP_FILE_SIZE_BYTES:
        raise ValidationError("Размер файла не должен превышать 20 МБ.")


class TripAttachment(UserOwnedModel):
    trip = models.ForeignKey(
        "Trip",
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="Рейс",
    )
    file = models.FileField(
        upload_to=trip_attachment_upload_to,
        validators=[
            FileExtensionValidator(allowed_extensions=ALLOWED_TRIP_FILE_EXTENSIONS),
            validate_trip_file_size,
        ],
        verbose_name="Файл",
    )
    original_name = models.CharField(
        max_length=255,
        verbose_name="Оригинальное имя файла",
    )
    file_size = models.PositiveIntegerField(
        verbose_name="Размер файла (байт)",
    )

    class Meta:
        verbose_name = "Вложение рейса"
        verbose_name_plural = "Вложения рейса"
        ordering = ("-created_at",)

    def clean(self):
        super().clean()
        if not self.trip_id:
            return

        qs = TripAttachment.objects.filter(trip_id=self.trip_id)
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        if qs.count() >= MAX_FILES_PER_TRIP:
            raise ValidationError(
                f"К рейсу можно прикрепить не более {MAX_FILES_PER_TRIP} файлов."
            )

    def save(self, *args, **kwargs):
        if self.file and not self.original_name:
            self.original_name = self.file.name
        if self.file and not self.file_size:
            self.file_size = self.file.size

        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        storage = self.file.storage if self.file else None
        file_name = self.file.name if self.file else None

        result = super().delete(*args, **kwargs)

        if storage and file_name and storage.exists(file_name):
            storage.delete(file_name)

        return result

    def __str__(self):
        return f"{self.original_name} (рейс {self.trip_id})"
