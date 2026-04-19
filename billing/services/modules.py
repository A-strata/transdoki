"""
Подключение/отключение платных модулей (ТЗ §6.7).

Модуль — отдельная ежемесячная подписка поверх любого тарифа. Доступен
одинаково на всех планах.

Правила жизненного цикла (ТЗ §3.6):
- Подключение в середине месяца → pro rata от monthly_price за days_left.
- Отключение → модуль работает до current_period_end, деньги за оставшиеся
  дни не возвращаются. is_active=False сразу; ended_at = период-end.
- charge_monthly списывает только за is_active=True. Отключённый модуль
  больше не попадает в списание следующего периода.

activate_module идемпотентно: повторный вызов при активном модуле —
no-op без повторного списания.
"""
import logging
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from billing.exceptions import InsufficientFunds, ModuleOperationError
from billing.models import AccountModule, BillingTransaction, Module
from billing.services.plan_change import _charge_balance, _pro_rata


logger = logging.getLogger("billing")


def _get_module_or_raise(module_code: str) -> Module:
    try:
        return Module.objects.get(code=module_code, is_active=True)
    except Module.DoesNotExist as exc:
        raise ModuleOperationError(
            f"Модуль {module_code!r} не найден или неактивен"
        ) from exc


def activate_module(account, module_code: str) -> dict:
    """
    Подключает модуль. Списывает pro rata от monthly_price за оставшиеся
    дни текущего периода подписки.

    Идемпотентно: если модуль уже активен — возвращает already_active=True,
    повторного списания нет.

    Реактивация после deactivate_module: повторное использование записи
    AccountModule (is_active становится True, ended_at сбрасывается).

    Returns:
        {'module_code': str, 'charged': Decimal, 'already_active': bool}

    Raises:
        ModuleOperationError — модуль не существует / неактивен в каталоге
        InsufficientFunds — на балансе не хватает pro rata-суммы
    """
    module = _get_module_or_raise(module_code)
    subscription = account.subscription

    existing = AccountModule.objects.filter(account=account, module=module).first()
    if existing and existing.is_active:
        return {
            "module_code": module.code,
            "charged": Decimal("0"),
            "already_active": True,
        }

    now = timezone.now()
    total_days = (subscription.current_period_end - subscription.current_period_start).days
    days_left = (subscription.current_period_end - now).days
    pro_rata = _pro_rata(module.monthly_price, days_left, total_days)

    if pro_rata > 0 and account.balance < pro_rata:
        raise InsufficientFunds(
            f"Для подключения модуля «{module.name}» требуется {pro_rata} ₽, "
            f"на балансе: {account.balance} ₽. Пополните баланс."
        )

    with transaction.atomic():
        if pro_rata > 0:
            _charge_balance(
                account,
                pro_rata,
                BillingTransaction.Kind.MODULE,
                description=f"Подключение модуля «{module.name}» (pro rata)",
            )

        if existing:
            # Реактивация — переиспользуем запись, чтобы сохранить started_at
            # и upgrade_at в истории. started_at остаётся первоначальной датой.
            existing.is_active = True
            existing.ended_at = None
            existing.save(update_fields=["is_active", "ended_at"])
            am = existing
        else:
            am = AccountModule.objects.create(
                account=account, module=module, is_active=True,
            )

    logger.info(
        "modules.activate account_id=%s module=%s charged=%s reactivated=%s",
        account.pk, module.code, pro_rata, bool(existing),
    )
    return {
        "module_code": module.code,
        "charged": pro_rata,
        "already_active": False,
        "reactivated": bool(existing),
    }


def deactivate_module(account, module_code: str) -> dict:
    """
    Отключает модуль. Модуль продолжает работать до конца текущего периода;
    в следующем charge_monthly списания за него не будет.

    Возврат средств за неиспользованные дни не производится (ТЗ §3.6).

    Идемпотентно: повторный вызов при уже отключённом модуле — no-op.

    Returns:
        {'module_code': str, 'active_until': datetime | None, 'already_inactive': bool}
    """
    am = AccountModule.objects.filter(
        account=account, module__code=module_code, is_active=True,
    ).select_related("module").first()

    if not am:
        return {"module_code": module_code, "already_inactive": True}

    subscription = account.subscription
    am.ended_at = subscription.current_period_end
    am.is_active = False
    am.save(update_fields=["is_active", "ended_at"])

    logger.info(
        "modules.deactivate account_id=%s module=%s active_until=%s",
        account.pk, module_code, am.ended_at,
    )
    return {
        "module_code": module_code,
        "active_until": am.ended_at,
        "already_inactive": False,
    }


class ModuleRequiredMixin:
    """
    Mixin для views, требующих активного модуля.

    Отличается от существующего billing.mixins.ModuleRequiredMixin тем, что:
    - Работает через новую модель AccountModule (FK на Module)
    - Проверяет is_active, не expires_at (старое поле удалено в миграции 0006)
    - Редиректит на страницу подписки (когда появится в итерации 5),
      пока — на кабинет

    Usage:
        class EdoDocumentsView(ModuleRequiredMixin, LoginRequiredMixin, ListView):
            required_module_code = "edo"
    """

    required_module_code: str | None = None
    module_blocked_url_name = "accounts:cabinet"

    def dispatch(self, request, *args, **kwargs):
        if not self.required_module_code:
            raise ImproperlyConfigured(
                f"{type(self).__name__}.required_module_code не задан"
            )

        if request.user.is_authenticated:
            from transdoki.tenancy import get_request_account
            from billing.services.balance import account_has_module

            account = get_request_account(request)
            if not account_has_module(
                account, self.required_module_code, request=request
            ):
                messages.info(
                    request,
                    "Этот раздел требует подключения модуля. "
                    "Подключите его на странице подписки.",
                )
                return redirect(reverse(self.module_blocked_url_name))

        return super().dispatch(request, *args, **kwargs)
