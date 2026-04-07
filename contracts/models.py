from django.conf import settings
from django.db import models

from transdoki.models import UserOwnedModel


def contract_template_upload_to(instance, filename):
    return f"contract_templates/{instance.account_id}/{instance.template_type}.docx"


class ContractTemplate(models.Model):
    """Пользовательский DOCX-шаблон документа. Один шаблон на тип на аккаунт."""

    TEMPLATE_TYPE_CHOICES = [
        ("contract", "Договор"),
        ("specification", "Спецификация"),
        ("addendum", "Дополнительное соглашение"),
        ("order_request", "Договор-заявка"),
    ]

    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        verbose_name="Аккаунт",
    )
    template_type = models.CharField(
        max_length=20,
        choices=TEMPLATE_TYPE_CHOICES,
        verbose_name="Тип шаблона",
    )
    file = models.FileField(
        upload_to=contract_template_upload_to,
        verbose_name="Файл шаблона",
    )
    uploaded_at = models.DateTimeField(auto_now=True, verbose_name="Дата загрузки")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Кто загрузил",
    )

    class Meta:
        unique_together = [("account", "template_type")]
        verbose_name = "Шаблон документа"
        verbose_name_plural = "Шаблоны документов"

    def __str__(self):
        return f"{self.get_template_type_display()} — {self.account}"


class Contract(UserOwnedModel):
    """Договор с контрагентом."""

    CONTRACT_TYPE_CHOICES = [
        ("transport", "Перевозка"),
        ("supply", "Поставка"),
        ("services", "Услуги"),
        ("agency", "Агентский"),
        ("other", "Иной"),
    ]

    STATUS_CHOICES = [
        ("draft", "Черновик"),
        ("active", "Действующий"),
        ("expired", "Истёк"),
        ("terminated", "Расторгнут"),
    ]

    number = models.CharField(max_length=50, verbose_name="Номер договора")
    contract_type = models.CharField(
        max_length=20,
        choices=CONTRACT_TYPE_CHOICES,
        default="transport",
        verbose_name="Тип договора",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        verbose_name="Статус",
    )
    own_company = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="contracts_as_own",
        verbose_name="Наша организация",
    )
    contractor = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="contracts_as_contractor",
        verbose_name="Контрагент",
    )
    date_signed = models.DateField(verbose_name="Дата подписания")
    valid_until = models.DateField(
        null=True, blank=True, verbose_name="Действует до"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Сумма",
    )
    subject = models.TextField(verbose_name="Предмет договора")
    notes = models.TextField(blank=True, default="", verbose_name="Примечания")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["account", "number"],
                name="unique_contract_number_per_account",
            ),
        ]
        ordering = ["-date_signed", "-pk"]
        verbose_name = "Договор"
        verbose_name_plural = "Договоры"

    def __str__(self):
        return f"Договор №{self.number} от {self.date_signed:%d.%m.%Y}"


class ContractAttachment(UserOwnedModel):
    """Дочерний документ договора (спецификация, допсоглашение, заявка)."""

    ATTACHMENT_TYPE_CHOICES = [
        ("specification", "Спецификация"),
        ("addendum", "Дополнительное соглашение"),
        ("order_request", "Договор-заявка"),
    ]

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="Договор",
    )
    attachment_type = models.CharField(
        max_length=20,
        choices=ATTACHMENT_TYPE_CHOICES,
        default="specification",
        verbose_name="Тип документа",
    )
    number = models.CharField(max_length=50, verbose_name="Номер")
    date_signed = models.DateField(verbose_name="Дата")
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Сумма",
    )
    subject = models.TextField(verbose_name="Предмет")
    notes = models.TextField(blank=True, default="", verbose_name="Примечания")

    class Meta:
        ordering = ["-date_signed", "-pk"]
        verbose_name = "Приложение к договору"
        verbose_name_plural = "Приложения к договорам"

    def __str__(self):
        return (
            f"{self.get_attachment_type_display()} №{self.number}"
            f" к договору №{self.contract.number}"
        )
