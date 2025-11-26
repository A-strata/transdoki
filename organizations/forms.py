from django import forms

from vehicles.models import Vehicle

from .models import Organization


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        exclude = ['created_by', 'created_at', 'updated_at', 'is_own_company']


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ['grn', 'brand', 'model', 'vehicle_type', 'property_type']


VehicleFormSet = forms.inlineformset_factory(
    Organization,
    Vehicle,
    form=VehicleForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=True
)
