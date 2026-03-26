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
        error_messages={"required": "Заполните это поле"},
        required=True,
    )

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
