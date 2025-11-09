from django import forms
from .models import Organization
from .validators import validate_inn

class OrganizationForm(forms.ModelForm):  
    class Meta:
        model = Organization
        fields = '__all__'
