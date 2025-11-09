from django.db import models

FIO_LENGTH = 150
NAME_LENGTH = 50
PHONE_LENGTH = 13


class Person(models.Model):
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
