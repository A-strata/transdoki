from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, UniqueConstraint
from django.urls import reverse
from django_cryptography.fields import encrypt

from transdoki.models import TenantManager, TenantQuerySet, UserOwnedModel  # noqa: F401

from .validators import validate_inn


class OrganizationQuerySet(TenantQuerySet):
    def own_for(self, account):
        if account is None:
            return self.none()
        return self.filter(account=account, is_own_company=True).order_by(
            "created_at", "pk"
        )


class OrganizationManager(TenantManager):
    def get_queryset(self):
        return OrganizationQuerySet(self.model, using=self._db)

    def own_for(self, account):
        return self.get_queryset().own_for(account)

ORG_NAME_LENGTH = 200
INN_LENGTH = 12
KPP_LENGTH = 9
OGRN_LENGTH = 15
ORG_ADDRESS_LENGTH = 200
BIC_LENGTH = 9
ACCOUNT_LENGTH = 20


class Organization(UserOwnedModel):
    """Заказчики, экспедиторы, перевозчики."""

    full_name = models.CharField(
        max_length=ORG_NAME_LENGTH,
        verbose_name="Полное наименование",
    )
    short_name = models.CharField(
        max_length=ORG_NAME_LENGTH,
        verbose_name="Сокращённое наименование",
    )
    inn = models.CharField(
        max_length=INN_LENGTH,
        validators=[validate_inn],
        verbose_name="ИНН",
    )
    kpp = models.CharField(
        max_length=KPP_LENGTH,
        verbose_name="КПП",
        null=True,
        blank=True,
    )
    ogrn = models.CharField(
        max_length=OGRN_LENGTH,
        verbose_name="ОГРН",
        null=True,
        blank=True,
    )
    address = models.CharField(
        max_length=ORG_ADDRESS_LENGTH,
        blank=True,
        null=True,
        verbose_name="Юридический адрес",
    )
    postal_address = models.CharField(
        max_length=ORG_ADDRESS_LENGTH,
        blank=True,
        default="",
        verbose_name="Почтовый адрес",
    )
    phone = models.CharField(
        max_length=25,
        blank=True,
        default="",
        verbose_name="Телефон",
    )
    email = models.EmailField(
        blank=True,
        default="",
        verbose_name="Email",
    )
    director_title = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Должность руководителя",
    )
    director_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
        verbose_name="ФИО руководителя",
    )
    is_own_company = models.BooleanField(default=False, verbose_name="Моя компания")
    petrolplus_integration_enabled = models.BooleanField(
        "ППР (Petrol Plus)", default=False
    )
    petrolplus_client_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    petrolplus_client_secret = encrypt(
        models.CharField(
            max_length=512,
            blank=True,
            null=True,
        )
    )
    petrolplus_credentials_updated_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    objects = OrganizationManager()

    def get_absolute_url(self):
        return reverse("organizations:edit", kwargs={"pk": self.pk})

    def __str__(self):
        return self.short_name

    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"
        constraints = [
            # Основная tenant-уникальность: в рамках account
            models.UniqueConstraint(
                fields=["account", "inn"],
                name="unique_inn_per_account",
                violation_error_message="Организация с таким ИНН уже существует.",
            ),
            # Бизнес-правило: "собственная компания" (is_own_company=True)
            # с таким ИНН может быть только одна на всю БД
            models.UniqueConstraint(
                fields=["inn"],
                condition=Q(is_own_company=True),
                name="unique_own_company_inn_global",
                violation_error_message="Компания с таким ИНН уже зарегистрирована в системе.",
            ),
        ]

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class OrganizationContact(UserOwnedModel):
    """Контактное лицо организации (справочник)."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="contacts",
        verbose_name="Организация",
    )
    name = models.CharField(max_length=150, verbose_name="ФИО")
    phone = models.CharField(max_length=25, blank=True, default="", verbose_name="Телефон")
    position = models.CharField(max_length=100, blank=True, default="", verbose_name="Должность")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Контактное лицо"
        verbose_name_plural = "Контактные лица"


class Bank(models.Model):
    bank_name = models.CharField(
        max_length=ORG_NAME_LENGTH,
        verbose_name="Наименование банка",
    )
    bic = models.CharField(
        max_length=BIC_LENGTH,
        verbose_name="БИК",
        unique=True,
    )
    corr_account = models.CharField(
        max_length=ACCOUNT_LENGTH,
        verbose_name="Корреспондентский счёт",
    )

    def __str__(self):
        return f"{self.bic} — {self.bank_name}"

    class Meta:
        verbose_name = "Банк"
        verbose_name_plural = "Банки"


class OrganizationBank(UserOwnedModel):
    account_num = models.CharField(
        max_length=ACCOUNT_LENGTH,
        verbose_name="Расчётный счёт",
    )
    account_owner = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        verbose_name="Владелец счёта",
        related_name="bank_accounts",
    )
    account_bank = models.ForeignKey(
        Bank,
        on_delete=models.CASCADE,
        verbose_name="Банк",
    )

    def clean(self):
        super().clean()

        if not self.account_num.isdigit() or len(self.account_num) != 20:
            raise ValidationError(
                {"account_num": "Расчётный счёт должен состоять из 20 цифр."}
            )

        if self.account_bank_id:
            try:
                bank = Bank.objects.get(pk=self.account_bank_id)
                bic = bank.bic
                if len(bic) != 9 or not bic.isdigit():
                    raise ValidationError(
                        {"account_bank": "БИК должен состоять из 9 цифр."}
                    )

                bic_rs = bic[-3:] + self.account_num
                weights = [
                    7,
                    1,
                    3,
                    7,
                    1,
                    3,
                    7,
                    1,
                    3,
                    7,
                    1,
                    3,
                    7,
                    1,
                    3,
                    7,
                    1,
                    3,
                    7,
                    1,
                    3,
                    7,
                    1,
                ]
                total = sum(int(bic_rs[i]) * weights[i] % 10 for i in range(23))

                if total % 10 != 0:
                    raise ValidationError(
                        {"account_num": "Неверное сочетание расчётного счёта и БИК."}
                    )

            except Bank.DoesNotExist:
                pass

    def save(self, *args, **kwargs):
        if (
            not self.account_id
            and self.account_owner_id
            and self.account_owner.account_id
        ):
            self.account_id = self.account_owner.account_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account_num} ({self.account_owner.short_name})"

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["account_num", "account_bank"],
                name="unique_account_bank",
            )
        ]
        verbose_name = "Банковский счёт организации"
        verbose_name_plural = "Банковские счета организаций"
