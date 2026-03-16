from django import forms

from organizations.models import Organization
from vehicles.models import Vehicle
from .models import Waybill


class WaybillCreateForm(forms.ModelForm):
    # Явно задаём поле даты, чтобы браузер показывал date-input.
    date = forms.DateField(
        label='Дата',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    class Meta:
        model = Waybill
        # Только те поля, которые пользователь вводит при создании.
        fields = ['date', 'organization', 'truck', 'trailer', 'driver']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Без пользователя форма не должна давать доступ к связанным объектам.
        if not self.user or not self.user.is_authenticated:
            self._set_empty_querysets()
            return

        self._apply_queryset_filters()

        # Прицеп необязателен и на уровне UI это тоже должно быть явно.
        self.fields['trailer'].required = False

    def _set_empty_querysets(self):
        # Защитное поведение: если user не передан,
        # в списках выбора ничего не показываем.
        self.fields['organization'].queryset = Organization.objects.none()
        self.fields['truck'].queryset = Vehicle.objects.none()
        self.fields['trailer'].queryset = Vehicle.objects.none()

    def _apply_queryset_filters(self):
        # Только свои организации, которые являются своей компанией.
        self.fields['organization'].queryset = Organization.objects.filter(
            created_by=self.user,
            is_own_company=True,
        ).order_by('id')

        # Для автомобиля показываем только подходящие типы ТС пользователя.
        self.fields['truck'].queryset = Vehicle.objects.filter(
            created_by=self.user,
            vehicle_type__in=['truck', 'single'],
        ).order_by('id')

        # Для прицепа показываем только прицепы пользователя.
        self.fields['trailer'].queryset = Vehicle.objects.filter(
            created_by=self.user,
            vehicle_type='trailer',
        ).order_by('id')

    def clean(self):
        # Здесь оставляем только простую форменную валидацию,
        # специфичную для сценария ввода.
        cleaned_data = super().clean()

        truck = cleaned_data.get('truck')
        trailer = cleaned_data.get('trailer')

        if truck and trailer and truck.pk == trailer.pk:
            self.add_error(
                'trailer', 'Автомобиль и прицеп не могут совпадать.')

        return cleaned_data
