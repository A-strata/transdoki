from django.db import models

from organizations.models import UserOwnedModel

FIO_LENGTH = 150
NAME_LENGTH = 50
PHONE_LENGTH = 13


class Person(UserOwnedModel):
    """Водители, контактные лица, руководители"""

    name = models.CharField(
        max_length=NAME_LENGTH,
        verbose_name='Имя'
    )
    surname = models.CharField(
        max_length=NAME_LENGTH,
        verbose_name='Фамилия'
    )
    patronymic = models.CharField(
        max_length=NAME_LENGTH,
        verbose_name='Отчество'
    )
    phone = models.CharField(
        max_length=12,
        verbose_name='Номер телефона',
        default='70000000000'
    )

    def __str__(self):
        return f"{self.surname} {self.name} {self.patronymic}"

    class Meta:
        verbose_name = 'Человек'
        verbose_name_plural = 'Люди'
        constraints = [
            models.UniqueConstraint(
                fields=['surname', 'name', 'patronymic', 'created_by'],
                name='unique_fio_per_user'
            )
        ]
