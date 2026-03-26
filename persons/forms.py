from django import forms

from .models import Person

_DATE_WIDGET = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class PersonForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Зашифрованные CharField возвращают b'' вместо '' для пустых значений
        for name, value in self.initial.items():
            if value == b'':
                self.initial[name] = ''

    phone = forms.CharField(
        label="Номер телефона",
        required=True,
        widget=forms.TextInput(attrs={
            "type": "tel",
            "inputmode": "tel",
            "autocomplete": "tel",
        }),
    )

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

    class Meta:
        model = Person
        exclude = ["created_by", "account", "created_at", "updated_at"]

    def clean(self):
        cleaned_data = super().clean()

        for field in ["name", "surname", "patronymic"]:
            value = cleaned_data.get(field)
            if value:
                cleaned_data[field] = value.capitalize()
        return cleaned_data
