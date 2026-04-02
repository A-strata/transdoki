from django import forms
from django.core.exceptions import ValidationError

from organizations.models import Organization
from transdoki.forms import ErrorHighlightMixin

from .models import Vehicle
from .validators import validate_grn_by_type


class VehicleForm(ErrorHighlightMixin, forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ['grn', 'brand', 'model', 'vehicle_type', 'property_type']
        widgets = {
            'grn': forms.TextInput(attrs={"data-grn-mask": ""}),
        }

    def clean(self):
        cleaned_data = super().clean()
        grn = cleaned_data.get('grn')
        vehicle_type = cleaned_data.get('vehicle_type')

        if grn:
            cleaned_data['grn'] = grn.upper()
            grn = grn.upper()

        if grn and vehicle_type:
            try:
                validate_grn_by_type(grn, vehicle_type)
            except ValidationError as e:
                self.add_error('grn', e)
            else:
                cleaned_data['grn'] = grn.upper()

        return cleaned_data


class VehicleFormWithOwner(VehicleForm):
    owner = forms.ModelChoiceField(
        queryset=Organization.objects.none(),
        label='Собственник',
        empty_label='— Выберите организацию —',
    )

    def __init__(self, *args, account=None, **kwargs):
        super().__init__(*args, **kwargs)
        if account is not None:
            from django.urls import reverse
            self.fields['owner'].queryset = Organization.objects.filter(
                account=account,
            ).order_by('short_name')
            self.fields['owner'].widget.attrs['data-search-url'] = reverse('organizations:search')
            # Предзаполнение: первая собственная компания
            if not self.initial.get('owner'):
                first_own = Organization.objects.filter(
                    account=account, is_own_company=True,
                ).order_by('pk').first()
                if first_own:
                    self.initial['owner'] = first_own.pk

    class Meta(VehicleForm.Meta):
        fields = ['owner', 'grn', 'brand', 'model', 'vehicle_type', 'property_type']
