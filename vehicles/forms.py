from django import forms
from django.core.exceptions import ValidationError

from .models import Vehicle
from .validators import validate_grn_by_type


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = "__all__"

    
    def clean(self):
        cleaned_data = super().clean()
        grn = cleaned_data.get('grn')
        vehicle_type = cleaned_data.get('vehicle_type')
        
        if grn and vehicle_type:
            try:
                validate_grn_by_type(grn, vehicle_type)
            except ValidationError as e:
                # Явно привязываем ошибку к полю grn
                self.add_error('grn', e)
        
        return cleaned_data
