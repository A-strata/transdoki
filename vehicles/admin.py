# vehicles/admin.py
from django.contrib import admin
from .models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('grn',
                    'brand',
                    'model',
                    'vehicle_type',
                    'status',
                    'owner',
                    'created_by')
    list_filter = ('vehicle_type', 'status', 'property_type', 'created_by')
    search_fields = ('grn', 'brand', 'model')
