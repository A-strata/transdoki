from django.db import models
from django_cryptography.fields import encrypt

from organizations.models import UserOwnedModel

from .validators import validate_phone_number

FIO_LENGTH = 150
NAME_LENGTH = 50
PHONE_LENGTH = 13


class Person(UserOwnedModel):
    """Водители, контактные лица, руководители"""

    name = models.CharField(max_length=NAME_LENGTH, verbose_name="Имя")
    surname = models.CharField(max_length=NAME_LENGTH, verbose_name="Фамилия")
    patronymic = models.CharField(max_length=NAME_LENGTH, verbose_name="Отчество")
    phone = models.CharField(
        max_length=25, verbose_name="Номер телефона", validators=[validate_phone_number]
    )

    employer = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employees",
        verbose_name="Работодатель",
    )

    # Персональные данные (шифруются at-rest, ФЗ-152)
    birth_date = encrypt(models.DateField(null=True, blank=True, verbose_name="Дата рождения"))

    # Паспорт
    passport_series = encrypt(
        models.CharField(max_length=4, blank=True, verbose_name="Серия паспорта")
    )
    passport_number = encrypt(
        models.CharField(max_length=6, blank=True, verbose_name="Номер паспорта")
    )
    passport_issued_by = encrypt(
        models.CharField(max_length=255, blank=True, verbose_name="Кем выдан")
    )
    passport_issued_date = encrypt(
        models.DateField(null=True, blank=True, verbose_name="Дата выдачи паспорта")
    )
    passport_department_code = encrypt(
        models.CharField(max_length=7, blank=True, verbose_name="Код подразделения")
    )

    # Водительское удостоверение
    license_number = encrypt(
        models.CharField(max_length=10, blank=True, verbose_name="Номер ВУ")
    )
    license_issued_date = encrypt(
        models.DateField(null=True, blank=True, verbose_name="Дата выдачи ВУ")
    )
    license_expiry_date = encrypt(
        models.DateField(null=True, blank=True, verbose_name="ВУ действует до")
    )
    license_categories = models.CharField(
        max_length=20, blank=True, verbose_name="Категории ВУ",
        help_text="Например: B, C, CE"
    )

    @property
    def is_own_employee(self):
        return self.employer_id is not None and self.employer.is_own_company

    def __str__(self):
        return f"{self.surname} {self.name} {self.patronymic}"

    class Meta:
        verbose_name = "Человек"
        verbose_name_plural = "Люди"
        constraints = [
            models.UniqueConstraint(
                fields=["surname", "name", "patronymic", "account"],
                name="unique_fio_per_account",
            ),
        ]
