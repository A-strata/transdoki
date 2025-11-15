from django import forms
from .models import Trip
from .validators import (
    validate_unique_trip_number_and_date,
    validate_client_cannot_be_carrier,
    validate_our_company_participation)


class TripForm(forms.ModelForm):
    class Meta:
        model = Trip
        exclude = ['created_by', 'created_at', 'updated_at']
        widgets = {
            'date_of_trip': forms.DateInput(
                attrs={'type': 'date'}),
            'planned_loading_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}),
            'planned_unloading_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}),
            'actual_loading_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}),
            'actual_unloading_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        # Извлекаем user из kwargs ДО вызова super()
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user and self.user.is_authenticated:
            self._apply_queryset_filters()

    def _apply_queryset_filters(self):
        """Применяем фильтрацию для всех ForeignKey полей"""
        from organizations.models import Organization
        from persons.models import Person
        from vehicles.models import Vehicle

        # Организации
        organization_qs = Organization.objects.filter(created_by=self.user)
        self.fields['client'].queryset = organization_qs
        self.fields['consignor'].queryset = organization_qs
        self.fields['consignee'].queryset = organization_qs
        self.fields['carrier'].queryset = organization_qs

        # Люди
        self.fields['driver'].queryset = Person.objects.filter(
            created_by=self.user)

        # Транспорт
        self.fields['truck'].queryset = Vehicle.objects.filter(
            created_by=self.user,
            vehicle_type__in=['truck', 'single']
        )
        self.fields['trailer'].queryset = Vehicle.objects.filter(
            created_by=self.user,
            vehicle_type='trailer'
        )

    def clean(self):
        """Валидация уникальности комбинации полей"""
        cleaned_data = super().clean()

        if self.user:
            # Валидация уникальности через отдельный валидатор
            validate_unique_trip_number_and_date(
                user=self.user,
                num_of_trip=cleaned_data.get('num_of_trip'),
                date_of_trip=cleaned_data.get('date_of_trip'),
                instance=self.instance
            )
            validate_client_cannot_be_carrier(
                client=cleaned_data.get('client'),
                carrier=cleaned_data.get('carrier')
            )
            validate_our_company_participation(
                client=cleaned_data.get('client'),
                consignor=cleaned_data.get('consignor'),
                consignee=cleaned_data.get('consignee'),
                carrier=cleaned_data.get('carrier')
            )

        return cleaned_data
