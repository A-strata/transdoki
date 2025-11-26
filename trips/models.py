from django.db import models

from organizations.models import Organization, UserOwnedModel
from persons.models import Person
from vehicles.models import Vehicle
from .validators import RussianMinValueValidator

CARGO_LENGTH = 20


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
        verbose_name='Стоимость заказа',
        blank=True,
        null=True,
        validators=[RussianMinValueValidator(0)],
        help_text='Общая стоимость заказа для клиента'
    )
    carrier_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Стоимость перевозки',
        blank=True,
        null=True,
        validators=[RussianMinValueValidator(0)],
        help_text='Общая стоимость заказа для перевозчика'
    )
    comments = models.TextField(
        max_length=1000,
        verbose_name='Комментарии',
        blank=True,
        help_text='Дополнительная информация о рейсе'
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
