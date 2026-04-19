"""
Mixins для views: проверка лимитов тарифа и модулей.

LimitCheckMixin — универсальная проверка can_create_* перед созданием
сущностей. Подкласс указывает callable, вызывающий один из
billing.services.limits.can_create_trip / organization / user.

ModuleRequiredMixin — проверка подключения платного модуля. Использует
новую модель AccountModule (FK на Module, is_active).

Старый BillingProtectedMixin удалён: проверка «balance > credit_limit»
заменена на per-entity-лимиты в подписочной модели (ТЗ §3.4, §3.8).
"""
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy

from billing.services import balance as billing_balance_service
from transdoki.tenancy import get_request_account


class LimitCheckMixin:
    """
    Mixin для CreateView: блокирует создание, если лимит тарифа превышен.

    Подкласс задаёт атрибут limit_check_callable — функцию с сигнатурой
    (account) -> tuple[bool, str]: из billing.services.limits.
    Если callable возвращает (False, msg) — redirect на limit_blocked_url
    c messages.error(msg). Для AJAX (X-Requested-With) возвращается
    JSON с HTTP 402 Payment Required.

    Exempt-аккаунты и отсутствующая подписка обрабатываются внутри
    can_create_* — миксин не дублирует эту логику.

    Usage:
        from billing.services.limits import can_create_trip

        class TripCreateView(LimitCheckMixin, LoginRequiredMixin, CreateView):
            limit_check_callable = staticmethod(can_create_trip)
    """

    limit_check_callable = None
    limit_blocked_url = reverse_lazy("accounts:cabinet")

    def dispatch(self, request, *args, **kwargs):
        if self.limit_check_callable is None:
            raise RuntimeError(
                f"{type(self).__name__}.limit_check_callable не задан"
            )

        if request.user.is_authenticated:
            account = get_request_account(request)
            ok, msg = self.limit_check_callable(account)
            if not ok:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse(
                        {"ok": False, "error": msg}, status=402
                    )
                messages.error(request, msg)
                return redirect(self.limit_blocked_url)

        return super().dispatch(request, *args, **kwargs)


class ModuleRequiredMixin:
    """
    Mixin: блокирует доступ к view, если модуль не подключён к аккаунту.

    Обновлён в итерации 4 под новую модель AccountModule (FK + is_active).
    Использует billing.services.balance.account_has_module, который
    кеширует список модулей на request.

    Usage:
        class EdoView(ModuleRequiredMixin, LoginRequiredMixin, ListView):
            required_module = "edo"
    """

    required_module: str = ""
    module_blocked_url = reverse_lazy("accounts:cabinet")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and self.required_module:
            account = get_request_account(request)
            if not billing_balance_service.account_has_module(
                account, self.required_module, request=request
            ):
                messages.error(
                    request,
                    "Этот раздел требует подключения модуля. "
                    "Подключите его на странице подписки.",
                )
                return redirect(self.module_blocked_url)
        return super().dispatch(request, *args, **kwargs)
