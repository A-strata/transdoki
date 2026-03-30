from django import forms

from transdoki.forms import ErrorHighlightMixin

from .models import Person

_DATE_WIDGET = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class PersonForm(ErrorHighlightMixin, forms.ModelForm):
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

    def clean_phone(self):
        value = self.cleaned_data.get("phone", "")
        digits = "".join(filter(str.isdigit, value))
        if not digits or digits == "7":
            raise forms.ValidationError("Заполните это поле")
        # Нормализация: 8-xxx → 7-xxx
        if digits.startswith("8") and len(digits) == 11:
            digits = "7" + digits[1:]
        if len(digits) != 11 or not digits.startswith("7"):
            raise forms.ValidationError("Введите корректный российский номер телефона")
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

    def clean(self):
        cleaned_data = super().clean()

        for field in ["name", "surname", "patronymic"]:
            value = cleaned_data.get(field)
            if value:
                cleaned_data[field] = value.capitalize()
        return cleaned_data
