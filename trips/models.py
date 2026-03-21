import uuid

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import IntegrityError, models, transaction

from organizations.models import Organization, UserOwnedModel
from persons.models import Person
from persons.validators import validate_phone_number
from vehicles.models import Vehicle

from .validators import RussianMinValueValidator

CARGO_LENGTH = 20
LOADING_TYPE_LENGTH = 20
TERM_OF_PAYMENT_LENGTH = 100
PAYMENT_TYPE_LENGTH = 50
ADDRESS_LENGTH = 200


class LoadingType(models.TextChoices):
    REAR = "rear", "Задняя"
    TOP = "top", "Верхняя"
    SIDE = "side", "Боковая"


class PaymentCondition(models.TextChoices):
    DOCUMENTS = (
        "documents",
        "По факту предоставления документов",
    )
    UNLOADING = "unloading", "По факту выгрузки"


class PaymentType(models.TextChoices):
    CASHLESS = "cashless", "Безналичный расчёт"
    CASH = "cash", "Наличный расчёт"


class Trip(UserOwnedModel):
    num_of_trip = models.PositiveSmallIntegerField(
        verbose_name="Номер заявки", editable=False
    )
    date_of_trip = models.DateField(verbose_name="Дата заявки", null=True, blank=True)
    client = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="trips_as_client",
        verbose_name="Заказчик перевозки",
    )
    consignor = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="trips_as_consignor",
        verbose_name="Отправитель",
    )
    consignee = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="trips_as_consignee",
        verbose_name="Получатель",
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
    planned_loading_date = models.DateTimeField(
        verbose_name="Заявленные дата и время погрузки"
    )
    planned_unloading_date = models.DateTimeField(
        verbose_name="Заявленные дата и время выгрузки"
    )
    actual_loading_date = models.DateTimeField(
        verbose_name="Фактическая дата и время погрузки", null=True, blank=True
    )
    actual_unloading_date = models.DateTimeField(
        verbose_name="Фактическая дата и время выгрузки", null=True, blank=True
    )
    loading_address = models.CharField(
        max_length=ADDRESS_LENGTH,
        verbose_name="Адрес погрузки",
    )
    unloading_address = models.CharField(
        max_length=ADDRESS_LENGTH,
        verbose_name="Адрес выгрузки",
    )
    loading_contact_name = models.CharField(
        max_length=150, blank=True, default="", verbose_name="Контакт на погрузке (имя)"
    )
    loading_contact_phone = models.CharField(
        max_length=25,
        blank=True,
        default="",
        verbose_name="Контакт на погрузке (телефон)",
        validators=[validate_phone_number],
    )
    unloading_contact_name = models.CharField(
        max_length=150, blank=True, default="", verbose_name="Контакт на выгрузке (имя)"
    )
    unloading_contact_phone = models.CharField(
        max_length=25,
        blank=True,
        default="",
        verbose_name="Контакт на выгрузке (телефон)",
        validators=[validate_phone_number],
    )
    cargo = models.CharField(max_length=CARGO_LENGTH, verbose_name="Груз")
    weight = models.PositiveIntegerField(verbose_name="Вес", blank=True, null=True)
    client_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Стоимость для клиента",
        blank=True,
        null=True,
        validators=[RussianMinValueValidator(0)],
    )
    carrier_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Стоимость для перевозчика",
        blank=True,
        null=True,
        validators=[RussianMinValueValidator(0)],
    )
    comments = models.TextField(
        max_length=1000,
        verbose_name="Комментарии",
        blank=True,
        help_text="Дополнительная информация о рейсе",
    )
    loading_type = models.CharField(
        max_length=LOADING_TYPE_LENGTH,
        choices=LoadingType.choices,
        blank=True,
        default="",
        verbose_name="Тип погрузки",
    )
    unloading_type = models.CharField(
        max_length=LOADING_TYPE_LENGTH,
        choices=LoadingType.choices,
        blank=True,
        default="",
        verbose_name="Тип выгрузки",
    )
    payment_type = models.CharField(
        max_length=PAYMENT_TYPE_LENGTH,
        choices=PaymentType.choices,
        blank=True,
        default="",
        verbose_name="Форма оплаты",
    )
    payment_condition = models.CharField(
        max_length=50,
        choices=PaymentCondition.choices,
        blank=True,
        default="",
        verbose_name="Условия оплаты",
    )
    payment_term = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Срок оплаты",
    )

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
