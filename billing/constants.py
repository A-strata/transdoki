from decimal import Decimal

# Бесплатный уровень (freemium) — дефолтные значения для новых аккаунтов
FREE_TIER_ORGS = 1
FREE_TIER_VEHICLES = 2
FREE_TIER_USERS = 2

# Тарифы сверх бесплатного уровня (₽/сутки)
DAILY_RATE_ORG = Decimal("15.00")
DAILY_RATE_VEHICLE = Decimal("10.00")
DAILY_RATE_USER = Decimal("5.00")

# Порог баланса для блокировки создания новых сущностей
BLOCK_THRESHOLD = Decimal("-500.00")

# Лимит активных сессий на одного пользователя
MAX_SESSIONS_PER_USER = 3

# Платные модули (код → отображаемое название)
# Добавлять новые модули сюда, не в модель.
AVAILABLE_MODULES = {
    "contracts": "Договоры",
}
