from django.db import models
from django.urls import reverse
from django.db.models import UniqueConstraint
from django.core.exceptions import ValidationError

ORG_NAME_LENGTH = 200
INN_LENGTH = 12
KPP_LENGTH = 9  # Исправлено: КПП всегда 9 цифр
OGRN_LENGTH = 15
ORG_ADDRESS_LENGTH = 200  # Исправлено: добавлено _LENGTH для консистентности
BIC_LENGTH = 9  # Исправлено: БИК всегда 9 цифр
ACCOUNT_LENGTH = 20


class Organization(models.Model):
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
        unique=True,
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
        unique=True,
        verbose_name="ОГРН",
    )
    address = models.CharField(
        max_length=ORG_ADDRESS_LENGTH,
        blank=True,
        null=True,
        verbose_name="Адрес юридического лица",
    )

    def get_absolute_url(self):
        return reverse("org_edit", kwargs={"pk": self.pk})
    
    def __str__(self):
        return self.short_name

    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"


class Bank(models.Model):
    bank_name = models.CharField(
        max_length=ORG_NAME_LENGTH,
        verbose_name="Наименование банка",
    )
    bic = models.CharField(
        max_length=BIC_LENGTH,
        verbose_name="БИК",
        unique=True,  # Добавлено: БИК должен быть уникальным
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


class OrganizationBank(models.Model):
    account_num = models.CharField(
        max_length=ACCOUNT_LENGTH,
        verbose_name="Расчётный счёт",
    )
    account_owner = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        verbose_name="Владелец счёта",
        related_name="bank_accounts",  # Добавлено для обратной связи
    )
    account_bank = models.ForeignKey(
        Bank,
        on_delete=models.CASCADE,
        verbose_name="Банк",
    )

    def clean(self):
        super().clean()
        
        # Проверка расчётного счёта
        if not self.account_num.isdigit() or len(self.account_num) != 20:
            raise ValidationError(
                {"account_num": "Расчётный счёт должен состоять из 20 цифр."}
            )

        # Проверка БИК (только если банк уже сохранен в БД)
        if self.account_bank_id:  # Проверяем по ID, чтобы избежать лишних запросов
            try:
                bank = Bank.objects.get(pk=self.account_bank_id)
                bic = bank.bic
                if len(bic) != 9 or not bic.isdigit():
                    raise ValidationError(
                        {"account_bank": "БИК банка должен состоять из 9 цифр."}
                    )
                
                # Проверка контрольной суммы
                bic_rs = bic[-3:] + self.account_num
                weights = [7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1]
                total = sum(int(bic_rs[i]) * weights[i] % 10 for i in range(23))
                
                if total % 10 != 0:
                    raise ValidationError(
                        {"account_num": "Неверное сочетание расчётного счёта и БИК."}
                    )
                    
            except Bank.DoesNotExist:
                pass  # Банк не найден, проверка будет при сохранении

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
