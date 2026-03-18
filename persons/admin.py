# persons/admin.py
from django.contrib import admin
from .models import Person


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'phone', 'created_by')
    search_fields = ('surname', 'name', 'patronymic', 'phone')
    list_filter = ('created_by',)

    @admin.display(description='ФИО')
    def get_full_name(self, obj):
        return f"{obj.surname} {obj.name} {obj.patronymic}"
