from django import forms

from .models import Organization


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        exclude = ['created_by', 'created_at', 'updated_at']
