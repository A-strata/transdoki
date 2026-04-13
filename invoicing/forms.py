from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import inlineformset_factory
from django.urls import reverse_lazy

from organizations.models import Organization, OrganizationBank
from transdoki.enums import VatRate

from .models import Invoice, InvoiceLine

# Служебные ключи cleaned_data формсета, которые не нужно передавать
# в InvoiceLine(**payload) при сохранении через сервис:
#   id      — служебное поле формсета (InvoiceLine instance | None)
#   DELETE  — служебный чекбокс can_delete=True
#   invoice — FK на родителя, автоматически добавляемый inlineformset_factory;
#             сервис сам проставляет invoice=invoice, поэтому из payload
#             его нужно убрать (иначе TypeError: multiple values for 'invoice')
LINE_META_KEYS = frozenset({"id", "DELETE", "invoice"})


class InvoiceForm(forms.ModelForm):
    """
    Форма шапки счёта. Используется и для создания, и для редактирования.

    account — обязательный kwarg, фильтрует queryset'ы customer
    и bank_account в пределах тенанта.
    """

    class Meta:
        model = Invoice
        fields = ["number", "date", "payment_due", "customer", "bank_account"]
        widgets = {
            # format="%Y-%m-%d" обязателен для <input type="date">:
            # HTML5 date-input принимает только ISO-формат. Без явного
            # format виджет использует локализацию (dd.mm.yyyy), браузер
            # такой value отклоняет и показывает пустое поле.
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "payment_due": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "number": forms.NumberInput(attrs={"min": "1"}),
        }

    def __init__(self, *args, account=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Номер — необязательное поле на уровне формы:
        # - create: пусто → сервис сгенерирует Max+1
        # - edit:   пусто → сервис сохранит исходный номер
        # Модель держит number обязательным (NOT NULL), обязательность
        # закрывается на уровне сервиса, а не формы.
        self.fields["number"].required = False

        if account is None:
            return

        # ── Customer: autocomplete через organizations:search ──────────
        # Рендерим <select> только с уже выбранным значением (или пустым),
        # чтобы не выгружать все сотни контрагентов в HTML. JS-скрипт
        # autocomplete.js оборачивает <select> в поисковый input и
        # подгружает остальных через AJAX по data-search-url.
        #
        # queryset переключается в зависимости от состояния формы:
        #   bound (POST)    — только posted pk, отфильтрованный по tenant;
        #                     обеспечивает валидацию выбора пользователя.
        #   unbound (GET)   — только instance.customer или initial.customer
        #                     или пусто; рендер выдаёт <= 1 <option>.
        # Tenant-ограничение сохраняется в обеих ветках.
        customer_field = self.fields["customer"]
        account_customers = Organization.objects.for_account(account)

        if self.is_bound:
            posted_pk = self.data.get(self.add_prefix("customer"))
            customer_field.queryset = (
                account_customers.filter(pk=posted_pk)
                if posted_pk
                else account_customers.none()
            )
        else:
            initial_pk = None
            if self.instance and self.instance.pk and self.instance.customer_id:
                initial_pk = self.instance.customer_id
            elif "customer" in self.initial:
                init_val = self.initial["customer"]
                initial_pk = init_val.pk if hasattr(init_val, "pk") else init_val

            customer_field.queryset = (
                account_customers.filter(pk=initial_pk)
                if initial_pk
                else account_customers.none()
            )

        customer_field.widget.attrs.update({
            "data-search-url": reverse_lazy("organizations:search"),
        })

        own = Organization.objects.filter(
            account=account,
            is_own_company=True,
        ).first()
        if not own:
            self.fields["bank_account"].queryset = OrganizationBank.objects.none()
            return

        bank_qs = OrganizationBank.objects.filter(account_owner=own).select_related(
            "account_bank"
        )
        self.fields["bank_account"].queryset = bank_qs
        # Поле обязательное на уровне формы. Модель оставлена nullable
        # (blank=True) — безопаснее для admin и исторических данных,
        # но в пользовательском потоке счёт без расчётного счёта
        # не создаётся.
        self.fields["bank_account"].required = True
        # Подпись в <option>: "р/с NNN (Название банка)".
        # Дефолтный __str__ у OrganizationBank показывает название
        # собственной компании, которое в контексте счёта избыточно —
        # компания одна и уже видна в шапке документа.
        self.fields["bank_account"].label_from_instance = lambda ba: (
            f"{ba.account_num} ({ba.account_bank.bank_name})"
        )

        # Предвыбор расчётного счёта при создании нового счёта: берём
        # первый банковский счёт собственной компании. Для edit Django
        # сам подставляет invoice.bank_account через instance — здесь
        # не вмешиваемся. Условие `"bank_account" not in self.initial`
        # уважает явный initial, переданный из view.
        #
        # TODO: когда появится OrganizationBank.is_primary —
        # выбирать банк с is_primary=True, с фоллбэком на первый.
        if not self.instance.pk and "bank_account" not in self.initial:
            first_bank = bank_qs.first()
            if first_bank:
                self.initial["bank_account"] = first_bank.pk


class InvoiceLineForm(forms.ModelForm):
    """
    Форма строки счёта.

    clean() делает пробный вызов instance.clean() ради поимки
    ValidationError из compute() с привязкой к полю строки.
    Результат мутации выбрасывается — сервис пересчитает на финальном
    объекте перед save(). Двойной вызов идемпотентен
    (см. InvoiceLine.compute docstring).
    """

    class Meta:
        model = InvoiceLine
        fields = [
            # trip — скрытое поле для привязки строки к рейсу при создании
            # счёта из рейсов. У ручных строк остаётся None.
            "trip",
            "description",
            "quantity",
            "unit",
            "unit_price",
            "discount_amount",
            "vat_rate",
        ]
        widgets = {
            "trip": forms.HiddenInput(),
            "description": forms.Textarea(
                attrs={
                    "class": "line-input line-input--desc",
                    "rows": 2,
                }
            ),
            "quantity": forms.TextInput(
                attrs={
                    "class": "line-input line-input--sm",
                    "data-line-qty": "",
                }
            ),
            "unit": forms.Select(
                attrs={
                    "class": "line-select",
                    "data-line-unit": "",
                }
            ),
            "unit_price": forms.TextInput(
                attrs={
                    "class": "line-input line-input--num",
                    "data-line-price": "",
                }
            ),
            "discount_amount": forms.TextInput(
                attrs={
                    "class": "line-input line-input--sm",
                    "data-line-disc-amt": "",
                }
            ),
            "vat_rate": forms.Select(
                attrs={
                    "class": "line-select",
                    "data-line-vat-select": "",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Подмена пустого варианта в дропдауне НДС: вместо дефолтного
        # "---------" — явное "Без НДС". vat_rate на модели IntegerField
        # с null=True → null означает «без НДС», а не «не выбрано».
        self.fields["vat_rate"].choices = [
            ("", "Без НДС"),
            *VatRate.choices,
        ]

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned

        # Пустая форма (extra=1 без заполнения) — не валидируем.
        # Django всё равно пропустит её через formset как empty_permitted.
        if not cleaned.get("unit_price"):
            return cleaned

        probe_kwargs = {k: v for k, v in cleaned.items() if k not in LINE_META_KEYS}
        probe = InvoiceLine(**probe_kwargs)
        try:
            probe.clean()
        except ValidationError as exc:
            if hasattr(exc, "error_dict"):
                for field, errors in exc.error_dict.items():
                    target = field if field in self.fields else None
                    self.add_error(target, errors)
            else:
                self.add_error(None, exc)

        return cleaned


# Для edit-режима: только существующие строки, без пустых форм.
# В view формсет инстанцируется как InvoiceLineFormSet(instance=invoice).
InvoiceLineFormSet = inlineformset_factory(
    Invoice,
    InvoiceLine,
    form=InvoiceLineForm,
    extra=0,
    can_delete=True,
)


# Для create-режима: одна пустая форма по умолчанию.
# При создании счёта из рейсов view использует initial= для префилла.
InvoiceLineFormSetNew = inlineformset_factory(
    Invoice,
    InvoiceLine,
    form=InvoiceLineForm,
    extra=1,
    can_delete=True,
)
