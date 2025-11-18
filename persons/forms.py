from django import forms

from .models import Person


class PersonForm(forms.ModelForm):
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
