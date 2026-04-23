"""
Единый реестр типов шаблонов/договоров/приложений.

Источник правды для:
- ContractTemplate.TEMPLATE_TYPE_CHOICES — все 6 типов шаблонов
- Contract.CONTRACT_TYPE_CHOICES — самостоятельные договоры (4 из 6)
- ContractAttachment.ATTACHMENT_TYPE_CHOICES — приложения (2 из 6)
- UI-метаданные на странице настроек шаблонов (section, badge, parent)
- Реестр плейсхолдеров (см. services.PLACEHOLDERS)

Метки должны совпадать с уже записанными в миграциях choices — иначе makemigrations
сгенерирует "бесполезную" AlterField. Если понадобится добавить новый тип, расширять
список TEMPLATES и прогонять makemigrations осознанно.
"""

from dataclasses import dataclass

SECTION_TRANSPORT = "transport"
SECTION_SUPPLY = "supply"

SECTIONS: list[tuple[str, str]] = [
    (SECTION_TRANSPORT, "Перевозки"),
    (SECTION_SUPPLY, "Поставки"),
]


@dataclass(frozen=True)
class TemplateSpec:
    """Описание одного типа документа (шаблона)."""

    code: str
    """Машинный код — используется как template_type, contract_type, attachment_type."""

    template_label: str
    """Человеческое название шаблона (для TEMPLATE_TYPE_CHOICES)."""

    section: str
    """Секция на странице настроек шаблонов: transport | supply."""

    badge: str
    """UI-бейдж на странице настроек: Рамочный | Дочерний | Самостоятельный."""

    parent: str | None = None
    """Код родительского шаблона для дочерних типов (приложений)."""

    contract_type_label: str | None = None
    """Метка, если код является типом договора (Contract.CONTRACT_TYPE_CHOICES).
    None — значит, этот код только для приложения, не для договора."""

    attachment_type_label: str | None = None
    """Метка, если код является типом приложения (ContractAttachment.ATTACHMENT_TYPE_CHOICES).
    None — значит, этот код только для договора, не для приложения."""

    @property
    def is_attachment(self) -> bool:
        return self.attachment_type_label is not None


TEMPLATES: tuple[TemplateSpec, ...] = (
    TemplateSpec(
        code="transport_contract",
        template_label="Договор об организации перевозки грузов",
        section=SECTION_TRANSPORT,
        badge="Рамочный",
        contract_type_label="Перевозка (долгосрочный)",
    ),
    TemplateSpec(
        code="transport_request",
        template_label="Заявка на перевозку груза",
        section=SECTION_TRANSPORT,
        badge="Дочерний",
        parent="transport_contract",
        attachment_type_label="Заявка на перевозку груза",
    ),
    TemplateSpec(
        code="single_transport",
        template_label="Договор на перевозку (разовый)",
        section=SECTION_TRANSPORT,
        badge="Самостоятельный",
        contract_type_label="Перевозка (разовый)",
    ),
    TemplateSpec(
        code="order_request",
        template_label="Договор-заявка (разовый)",
        section=SECTION_TRANSPORT,
        badge="Самостоятельный",
        contract_type_label="Договор-заявка (разовый)",
    ),
    TemplateSpec(
        code="supply_contract",
        template_label="Договор поставки",
        section=SECTION_SUPPLY,
        badge="Рамочный",
        contract_type_label="Поставка",
    ),
    TemplateSpec(
        code="supply_spec",
        template_label="Спецификация",
        section=SECTION_SUPPLY,
        badge="Дочерний",
        parent="supply_contract",
        attachment_type_label="Спецификация",
    ),
)


TEMPLATE_TYPE_CHOICES: list[tuple[str, str]] = [
    (t.code, t.template_label) for t in TEMPLATES
]

CONTRACT_TYPE_CHOICES: list[tuple[str, str]] = [
    (t.code, t.contract_type_label)
    for t in TEMPLATES
    if t.contract_type_label is not None
]

ATTACHMENT_TYPE_CHOICES: list[tuple[str, str]] = [
    (t.code, t.attachment_type_label)
    for t in TEMPLATES
    if t.attachment_type_label is not None
]


def by_code(code: str) -> TemplateSpec | None:
    for t in TEMPLATES:
        if t.code == code:
            return t
    return None
