from django.conf import settings
from django.db import models

FIO_LENGTH = 150
NAME_LENGTH = 50
PHONE_LENGTH = 13


class UserOwnedModel(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        abstract = True


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

    def __str__(self):
        return f"{self.surname} {self.name} {self.patronymic}"

    class Meta:
        verbose_name = 'Человек'
        verbose_name_plural = 'Люди'
        constraints = [
            models.UniqueConstraint(
                fields=['surname', 'name', 'patronymic'],
                name='unique_person_full_name'
            )
        ]
