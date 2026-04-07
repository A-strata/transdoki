from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy

from billing import services as billing_services
from transdoki.tenancy import get_request_account


class BillingProtectedMixin:
    """
    Миксин для CreateView: блокирует создание сущностей,
    если баланс аккаунта достиг кредитного лимита.

    Использование:
        class MyCreateView(BillingProtectedMixin, LoginRequiredMixin, CreateView):
            ...
    """

    billing_blocked_url = reverse_lazy("accounts:cabinet")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            account = get_request_account(request)
            if not billing_services.can_create_entity(account):
                messages.error(
                    request,
                    "Создание новых записей заблокировано: баланс аккаунта "
                    f"ниже допустимого ({account.credit_limit} руб.). "
                    "Пополните счёт в личном кабинете.",
                )
                return redirect(self.billing_blocked_url)
        return super().dispatch(request, *args, **kwargs)


class ModuleRequiredMixin:
    """
    Миксин для views: блокирует доступ если модуль не подключён к аккаунту.

    Использование:
        class MyView(ModuleRequiredMixin, LoginRequiredMixin, ListView):
            required_module = "contracts"
    """

    required_module: str = ""
    module_blocked_url = reverse_lazy("accounts:cabinet")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and self.required_module:
            account = get_request_account(request)
            if not billing_services.account_has_module(
                account, self.required_module, request=request
            ):
                messages.error(
                    request,
                    "Этот раздел недоступен для вашего аккаунта. "
                    "Обратитесь к администратору для подключения.",
                )
                return redirect(self.module_blocked_url)
        return super().dispatch(request, *args, **kwargs)
