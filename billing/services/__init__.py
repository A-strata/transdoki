"""
Пакет сервисов биллинга.

Структура:
- balance.py      — deposit/withdraw, account_has_module, can_create_entity (legacy)
- usage.py        — get_trip_usage (24-часовое окно, confirmed/pending)
- limits.py       — лимиты орг/пользователей, can_create_trip/organization/user

Реэкспорт в __init__ сохраняет обратную совместимость: существующий код
`from billing import services as billing_services` продолжает работать с
функциями balance.py. Новые функции usage/limits импортируются явно
(`from billing.services import usage, limits`), чтобы не захламлять
публичный API пакета.
"""
from billing.services.balance import (  # noqa: F401
    account_has_module,
    can_create_entity,
    deposit,
    get_daily_cost,
    withdraw,
)
