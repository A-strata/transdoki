from django import forms

from .models import Trip


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
