from django.db import models
from persons.validators import validate_phone_number

from organizations.models import Organization, UserOwnedModel
from persons.models import Person
from vehicles.models import Vehicle

from .validators import RussianMinValueValidator

CARGO_LENGTH = 20
LOADING_TYPE_LENGTH = 20
TERM_OF_PAYMENT_LENGTH = 100
PAYMENT_TYPE_LENGTH = 50
ADDRESS_LENGTH = 200


class LoadingType(models.TextChoices):
    REAR = 'rear', 'Задняя'
    TOP = 'top', 'Верхняя'
    SIDE = 'side', 'Боковая'


class PaymentCondition(models.TextChoices):
    DOCUMENTS = 'documents', 'По факту предоставления документов',
    UNLOADING = 'unloading', 'По факту выгрузки'


class PaymentType(models.TextChoices):
    CASHLESS = 'cashless', 'Безналичный расчёт'
    CASH = 'cash', 'Наличный расчёт'


class Trip(UserOwnedModel):
    num_of_trip = models.PositiveSmallIntegerField(
        verbose_name='Номер заявки'
    )
    date_of_trip = models.DateField(
        verbose_name='Дата заявки',
        null=True,
        blank=True
    )
    client = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='trips_as_client',
        verbose_name='Заказчик перевозки'
    )
    consignor = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='trips_as_consignor',
        verbose_name='Отправитель'
    )
    consignee = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='trips_as_consignee',
        verbose_name='Получатель'
    )
    carrier = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='trips_as_carrier',
        verbose_name='Перевозчик'
    )
    driver = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name='trips_as_driver',
        verbose_name='Водитель'
    )
    truck = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name='trips_as_truck',
        verbose_name='Автомобиль'
    )
    trailer = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name='trips_as_trailer',
        verbose_name='Прицеп',
        blank=True,
        null=True
    )
    planned_loading_date = models.DateTimeField(
        verbose_name='Заявленные дата и время погрузки'
    )
    planned_unloading_date = models.DateTimeField(
        verbose_name='Заявленные дата и время выгрузки'
    )
    actual_loading_date = models.DateTimeField(
        verbose_name='Фактическая дата и время погрузки',
        null=True,
        blank=True
    )
    actual_unloading_date = models.DateTimeField(
        verbose_name='Фактическая дата и время выгрузки',
        null=True,
        blank=True
    )
    loading_address = models.CharField(
        max_length=ADDRESS_LENGTH,
        verbose_name='Адрес погрузки',
    )
    unloading_address = models.CharField(
        max_length=ADDRESS_LENGTH,
        verbose_name='Адрес выгрузки',
    )
    loading_contact_name = models.CharField(
        max_length=150,
        blank=True,
        default='',
        verbose_name='Контакт на погрузке (имя)'
    )
    loading_contact_phone = models.CharField(
        max_length=25,
        blank=True,
        default='',
        verbose_name='Контакт на погрузке (телефон)',
        validators=[validate_phone_number],
    )
    unloading_contact_name = models.CharField(
        max_length=150,
        blank=True,
        default='',
        verbose_name='Контакт на выгрузке (имя)'
    )
    unloading_contact_phone = models.CharField(
        max_length=25,
        blank=True,
        default='',
        verbose_name='Контакт на выгрузке (телефон)',
        validators=[validate_phone_number],
    )
    cargo = models.CharField(
        max_length=CARGO_LENGTH,
        verbose_name='Груз'
    )
    weight = models.PositiveIntegerField(
        verbose_name='Вес',
        blank=True,
        null=True
    )
    client_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Стоимость для клиента',
        blank=True,
        null=True,
        validators=[RussianMinValueValidator(0)],
    )
    carrier_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Стоимость для перевозчика',
        blank=True,
        null=True,
        validators=[RussianMinValueValidator(0)],
    )
    comments = models.TextField(
        max_length=1000,
        verbose_name='Комментарии',
        blank=True,
        help_text='Дополнительная информация о рейсе'
    )
    loading_type = models.CharField(
        max_length=LOADING_TYPE_LENGTH,
        choices=LoadingType.choices,
        blank=True,
        default='',
        verbose_name='Тип погрузки',
    )
    unloading_type = models.CharField(
        max_length=LOADING_TYPE_LENGTH,
        choices=LoadingType.choices,
        blank=True,
        default='',
        verbose_name='Тип выгрузки',

    )
    payment_type = models.CharField(
        max_length=PAYMENT_TYPE_LENGTH,
        choices=PaymentType.choices,
        blank=True,
        default='',
        verbose_name='Форма оплаты'
    )
    payment_condition = models.CharField(
        max_length=50,
        choices=PaymentCondition.choices,
        blank=True,
        default='',
        verbose_name='Условия оплаты'
    )
    payment_term = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name='Срок оплаты',
    )

    class Meta:
        verbose_name = "Рейс"
        verbose_name_plural = "Рейсы"
        constraints = [
            models.UniqueConstraint(
                fields=['created_by', 'num_of_trip', 'date_of_trip'],
                name='unique_num_and_date_per_user'
            )
        ]
