from django.contrib import admin
from django.core.exceptions import PermissionDenied

from transdoki.tenancy import get_request_account

from .models import Person


def _get_request_account(request):
    """
    Совместимость для admin:
    - используем общий tenancy helper
    - сохраняем прежнее поведение admin (если account не найден -> None)
    """
    try:
        return get_request_account(request)
    except PermissionDenied:
        return None


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("get_full_name", "phone", "account", "created_by")
    search_fields = ("surname", "name", "patronymic", "phone")
    list_filter = ("account",)

    @admin.display(description="ФИО")
    def get_full_name(self, obj):
        return f"{obj.surname} {obj.name} {obj.patronymic}"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        account = _get_request_account(request)
        if not account:
            return qs.none()
        return qs.filter(account=account)

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        if not obj.account_id:
            account = _get_request_account(request)
            if account:
                obj.account = account
        super().save_model(request, obj, form, change)
