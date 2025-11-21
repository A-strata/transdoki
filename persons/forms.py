from django import forms

from .models import Person
from .validators import validate_phone_number


class PersonForm(forms.ModelForm):
    phone = forms.CharField(
        max_length=25,
        required=True,
        label='Номер телефона',
        validators=[validate_phone_number],
        error_messages={
            'required': 'Обязательное поле'  # кастомное сообщение
        }
    )

    class Meta:
        model = Person
        exclude = ['created_by', 'created_at', 'updated_at']

    def clean(self):
        cleaned_data = super().clean()

        for field in ['name', 'surname', 'patronymic']:
            value = cleaned_data.get(field)
            if value:
                cleaned_data[field] = value.capitalize()

        return cleaned_data
