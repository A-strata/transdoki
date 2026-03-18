# trips/admin.py
from django.contrib import admin
from .models import Trip


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = (
        'num_of_trip',
        'date_of_trip',
        'client',
        'driver',
        'truck',
        'client_cost',
        'carrier_cost')
    list_filter = ('date_of_trip',
                   'payment_type',
                   'payment_condition',
                   'created_by')
    search_fields = (
        'num_of_trip',
        'client__short_name',
        'driver__surname',
        'truck__grn')
    readonly_fields = ('num_of_trip',)  # Так как номер генерируется в save()

    fieldsets = (
        ('Основная информация', {
            'fields': ('num_of_trip', 'date_of_trip', 'created_by')
        }),
        ('Участники', {
            'fields': (('client', 'carrier'),
                       ('consignor', 'consignee'),
                       ('driver', 'truck', 'trailer'))
        }),
        ('Логистика', {
            'fields': (('planned_loading_date', 'planned_unloading_date'),
                       ('loading_address', 'unloading_address'),
                       ('cargo', 'weight', 'loading_type', 'unloading_type'))
        }),
        ('Финансы и оплата', {
            'fields': (
                ('client_cost', 'carrier_cost'),
                ('payment_type', 'payment_condition', 'payment_term'))
        }),
    )
