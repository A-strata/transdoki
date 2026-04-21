from django import forms

from transdoki.forms import ErrorHighlightMixin

from .models import Person

_DATE_WIDGET = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class _PersonCleanMixin:
    """Общие cleaner-ы для форм, редактирующих Person.

    Содержит:
      * нормализацию телефона (через persons.services.normalize_phone),
      * capitalize для ФИО.

    Делегируется на clean_phone и clean(); обе формы (PersonForm и
    PersonQuickForm) получают единую реализацию. Это — защита от
    расхождений логики нормализации между основной формой и модалкой.
    """

    def clean_phone(self):
        # Локальный импорт — защита от циклов и лёгкости подмены в тестах.
        from .services import normalize_phone

        value = (self.cleaned_data.get("phone") or "").strip()
        if not value:
            if self.fields["phone"].required:
                raise forms.ValidationError("Заполните это поле")
            return ""
        return normalize_phone(value)

    def clean(self):
        cleaned_data = super().clean()
        for field in ("name", "surname", "patronymic"):
            value = cleaned_data.get(field)
            if value:
                cleaned_data[field] = value.capitalize()
        return cleaned_data


class PersonForm(_PersonCleanMixin, ErrorHighlightMixin, forms.ModelForm):
    passport_series_number = forms.CharField(
        label="Серия и номер паспорта",
        required=False,
        widget=forms.TextInput(attrs={"data-passport-mask": ""}),
    )

    def __init__(self, *args, **kwargs):
        kwargs.pop("force_own_employee", None)
        super().__init__(*args, **kwargs)

        # Зашифрованные CharField возвращают b'' вместо '' для пустых значений
        for name, value in self.initial.items():
            if value == b"":
                self.initial[name] = ""
        # Склеиваем серию и номер для отображения в маске
        series = getattr(self.instance, "passport_series", "") or ""
        number = getattr(self.instance, "passport_number", "") or ""
        if series or number:
            self.initial["passport_series_number"] = str(series) + str(number)

    phone = forms.CharField(
        label="Номер телефона",
        required=True,
        widget=forms.TextInput(
            attrs={
                "type": "tel",
                "data-phone-mask": "",
            }
        ),
    )

    passport_department_code = forms.CharField(
        label="Код подразделения",
        required=False,
        widget=forms.TextInput(
            attrs={
                "data-code-mask": "",
            }
        ),
    )

    def clean_passport_series_number(self):
        value = self.cleaned_data.get("passport_series_number", "")
        digits = "".join(filter(str.isdigit, value))
        if not digits:
            return ""
        if len(digits) != 10:
            raise forms.ValidationError("Введите серию и номер паспорта полностью")
        self.cleaned_data["passport_series"] = digits[:4]
        self.cleaned_data["passport_number"] = digits[4:]
        return digits

    birth_date = forms.DateField(
        label="Дата рождения",
        required=False,
        widget=_DATE_WIDGET,
    )
    passport_issued_date = forms.DateField(
        label="Дата выдачи паспорта",
        required=False,
        widget=_DATE_WIDGET,
    )
    license_issued_date = forms.DateField(
        label="Дата выдачи ВУ",
        required=False,
        widget=_DATE_WIDGET,
    )
    license_expiry_date = forms.DateField(
        label="ВУ действует до",
        required=False,
        widget=_DATE_WIDGET,
    )

    def save(self, commit=True):
        instance = super().save(commit=False)
        sn = self.cleaned_data.get("passport_series_number", "")
        digits = "".join(filter(str.isdigit, sn))
        instance.passport_series = digits[:4] if len(digits) == 10 else ""
        instance.passport_number = digits[4:] if len(digits) == 10 else ""
        if commit:
            instance.save()
        return instance

    class Meta:
        model = Person
        exclude = ["created_by", "account", "created_at", "updated_at",
                   "passport_series", "passport_number", "employer"]


class PersonQuickForm(_PersonCleanMixin, forms.ModelForm):
    """Форма для модалки быстрого создания водителя.

    Используется в двух местах:
      * карточка организации (organization_detail.html::create-person-form),
      * форма рейса (trip_form.html::qc-person-form).

    Оба шаблона POST-ят на persons:quick_create. Форма берёт на себя:
      * нормализацию телефона (через _PersonCleanMixin, единая с PersonForm);
      * валидацию employer как ForeignKey — tenant-фильтрация применяется
        во view, где есть request.account.

    Телефон опционален: в модалке водителя пользователь может не знать номер
    на момент создания. Если передан — нормализуется и валидируется; иначе
    сохраняется пустая строка.
    """

    phone = forms.CharField(
        label="Номер телефона",
        required=False,
        widget=forms.TextInput(attrs={"type": "tel", "data-phone-mask": ""}),
    )

    class Meta:
        model = Person
        fields = ["employer", "surname", "name", "patronymic", "phone"]
