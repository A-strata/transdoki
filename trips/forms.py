from django import forms

from .models import Trip
from .validators import (validate_client_cannot_be_carrier,
                         validate_costs_by_our_company_role,
                         validate_our_company_participation,
                         validate_trailer_for_truck,
                         validate_unique_trip_number_and_date,
                         validate_vehicles_belong_to_carrier)


class TripForm(forms.ModelForm):
    num_of_trip = forms.IntegerField(
        label='Номер заявки',
        required=False,
        disabled=True
    )

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

        # Показываем номер рейса только при редактировании
        if self.instance and self.instance.pk:
            self.fields['num_of_trip'].initial = self.instance.num_of_trip
        else:
            self.fields.pop('num_of_trip', None)

        if self.user and self.user.is_authenticated:
            self._apply_queryset_filters()

    def _apply_queryset_filters(self):
        """Применяем фильтрацию с сохранением текущих значений
        для полей, являющихся внешними ключами"""
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

    # ✅ ДОБАВЛЕНО: парная валидация контактов
    def _validate_contact_pair(
            self, cleaned_data, name_field, phone_field, place_label):
        name = (cleaned_data.get(name_field) or '').strip()
        phone = (cleaned_data.get(phone_field) or '').strip()

        # нормализуем значения после strip
        cleaned_data[name_field] = name
        cleaned_data[phone_field] = phone

        if bool(name) ^ bool(phone):
            msg = f'Для контакта на {place_label} заполните и имя, и телефон.'
            self.add_error(name_field, msg)
            self.add_error(phone_field, msg)

    def clean(self):
        cleaned_data = super().clean()

        # ✅ ДОБАВЛЕНО: валидация новых 4 полей (вне зависимости от user)
        self._validate_contact_pair(
            cleaned_data,
            'loading_contact_name',
            'loading_contact_phone',
            'погрузке'
        )
        self._validate_contact_pair(
            cleaned_data,
            'unloading_contact_name',
            'unloading_contact_phone',
            'выгрузке'
        )

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
            validate_trailer_for_truck(
                truck=cleaned_data.get('truck'),
                trailer=cleaned_data.get('trailer')
            )
            validate_vehicles_belong_to_carrier(
                truck=cleaned_data.get('truck'),
                trailer=cleaned_data.get('trailer'),
                carrier=cleaned_data.get('carrier')
            )
            validate_costs_by_our_company_role(
                client=cleaned_data.get('client'),
                carrier=cleaned_data.get('carrier'),
                client_cost=cleaned_data.get('client_cost'),
                carrier_cost=cleaned_data.get('carrier_cost'),
            )

        return cleaned_data
