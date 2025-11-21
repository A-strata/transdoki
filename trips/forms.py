from django import forms

from .models import Trip
from .validators import (validate_client_cannot_be_carrier,
                         validate_our_company_participation,
                         validate_unique_trip_number_and_date)


# trips/forms.py
class TripForm(forms.ModelForm):
    class Meta:
        model = Trip
        exclude = ['created_by', 'created_at', 'updated_at']
        widgets = {
            'date_of_trip': forms.DateInput(attrs={'type': 'date'}),
            'planned_loading_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local'}),
            'planned_unloading_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local'}),
            'actual_loading_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local'}),
            'actual_unloading_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user and self.user.is_authenticated:
            self._apply_queryset_filters()

    def _apply_queryset_filters(self):
        """Применяем фильтрацию с сохранением текущих значений"""
        from organizations.models import Organization
        from persons.models import Person
        from vehicles.models import Vehicle

        # Организации
        organization_qs = Organization.objects.filter(created_by=self.user)
        for field in ['client', 'consignor', 'consignee', 'carrier']:
            self.fields[field].queryset = self._add_current_value(
                organization_qs, field)

        # Люди
        person_qs = Person.objects.filter(created_by=self.user)
        self.fields['driver'].queryset = self._add_current_value(
            person_qs, 'driver')

        # Транспорт
        truck_qs = Vehicle.objects.filter(
            created_by=self.user, vehicle_type__in=['truck', 'single'])
        self.fields['truck'].queryset = self._add_current_value(
            truck_qs, 'truck')

        trailer_qs = Vehicle.objects.filter(
            created_by=self.user, vehicle_type='trailer')
        self.fields['trailer'].queryset = self._add_current_value(
            trailer_qs, 'trailer')

    def _add_current_value(self, base_queryset, field_name):
        """Добавляет текущее значение в queryset"""
        current_value = getattr(self.instance, field_name, None)
        if current_value:
            return base_queryset | base_queryset.model.objects.filter(
                pk=current_value.pk)
        return base_queryset

    def clean(self):
        cleaned_data = super().clean()

        if self.user:
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
