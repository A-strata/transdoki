from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, UniqueConstraint
from django.urls import reverse
from django_cryptography.fields import encrypt

from .validators import validate_inn

ORG_NAME_LENGTH = 200
INN_LENGTH = 12
KPP_LENGTH = 9
OGRN_LENGTH = 15
ORG_ADDRESS_LENGTH = 200
BIC_LENGTH = 9
ACCOUNT_LENGTH = 20


class UserOwnedModel(models.Model):
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.PROTECT,
        db_index=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


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
        verbose_name="Адрес юридического лица",
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
            ),
            # Бизнес-правило: "собственная компания" (is_own_company=True)
            # с таким ИНН может быть только одна на всю БД
            models.UniqueConstraint(
                fields=["inn"],
                condition=Q(is_own_company=True),
                name="unique_own_company_inn_global",
            ),
        ]

    def _resolve_limit(self) -> int:
        return self.account.max_own_companies

    def _own_companies_qs(self):
        return Organization.objects.filter(
            is_own_company=True,
            account_id=self.account_id,
        ).exclude(pk=self.pk)

    def clean(self):
        super().clean()

        if self.is_own_company:
            own_companies_count = self._own_companies_qs().count()
            limit = self._resolve_limit()

            if own_companies_count >= limit:
                raise ValidationError(
                    {
                        "is_own_company": (
                            f"Превышен лимит собственных компаний. "
                            f"Использовано {own_companies_count} из {limit}"
                        )
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


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
