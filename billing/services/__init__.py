"""
Пакет сервисов биллинга.

Структура:
- balance.py       — deposit/withdraw, account_has_module, get_daily_cost (legacy)
- usage.py         — get_trip_usage (24-часовое окно, confirmed/pending)
- limits.py        — лимиты орг/пользователей, can_create_trip/organization/user
- charging.py      — месячный биллинг (charge_monthly, advisory lock)
- plan_change.py   — upgrade_plan, schedule_downgrade, cancel_downgrade
- modules.py       — activate_module, deactivate_module, ModuleRequiredMixin
- lifecycle.py     — process_past_due_accounts

Реэкспорт в __init__ — минимальный набор для legacy-совместимости:
`from billing import services as billing_services` используется в
cloudpayments.py и context_processors.py для deposit/account_has_module.
Новые функции импортируются явно из подмодулей, чтобы избежать круговых
зависимостей и держать явный интерфейс.
"""
from billing.services.balance import (  # noqa: F401
    account_has_module,
    deposit,
    get_daily_cost,
    withdraw,
)
