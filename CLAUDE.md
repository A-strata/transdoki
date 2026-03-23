# transdoki — Django Project Guide for Claude

## Project overview
Transport document management system (путевые листы, рейсы, транспортные средства).
Production URL: transdoki.ru

## Stack
- Python 3.12, Django 5.2
- SQLite (dev) — db.sqlite3 в корне
- Gunicorn (production)
- Package manager: **Poetry** (`poetry run ...` или активированный venv)
- Linter/formatter: **ruff**

## Key dependencies
- `dadata` — подсказки адресов и реквизитов
- `docxtpl` — генерация .docx документов (путевые листы)
- `django-cryptography-5` — шифрование полей в БД
- `requests` — HTTP-клиент для интеграций
- `python-dotenv` — переменные окружения из .env

## Apps
| App | Назначение |
|-----|-----------|
| `accounts` | Аутентификация, профили, роли, сессии пользователей |
| `billing` | Биллинг: баланс аккаунта, транзакции, тарификация |
| `organizations` | Организации (юрлица) |
| `persons` | Физические лица (водители и др.) |
| `vehicles` | Транспортные средства |
| `trips` | Рейсы |
| `waybills` | Путевые листы |
| `integrations` | Внешние интеграции (Petrolplus и др.) |

## Structure per app (standard pattern)
```
<app>/
  models.py       # модели БД
  views.py        # CBV/FBV
  forms.py        # Django forms
  urls.py         # URL patterns
  services.py     # бизнес-логика (НЕ в views)
  admin.py        # Django admin
  validators.py   # кастомные валидаторы (если есть)
  tests.py        # тесты
  templates/<app>/  # шаблоны приложения
  migrations/     # миграции (не редактировать вручную)
```

## Commands
```bash
# Dev server
python manage.py runserver

# Migrations
python manage.py makemigrations
python manage.py migrate

# Tests
python manage.py test

# Linting (ruff)
ruff check .
ruff format .

# Shell
python manage.py shell

# Static files (production)
python manage.py collectstatic

# Ежедневное списание за использование (запускать через cron)
python manage.py charge_daily
python manage.py charge_daily --dry-run   # только расчёт, без записи в БД
```

## Secrets & Environment (.env)
Никогда не коммитить `.env`. Ключи берутся из `os.getenv()`:
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG` (True/False)
- `DJANGO_ALLOWED_HOSTS` (через запятую)
- `PETROLPLUS_AUTH_BASE_URL`, `PETROLPLUS_DATA_URL`
- `PETROLPLUS_CLIENT_ID`, `PETROLPLUS_CLIENT_SECRET`

## Coding conventions
- Бизнес-логика — в `services.py`, не в views и не в models
- Views максимально тонкие: валидация формы → вызов service → redirect/render
- Шаблоны: `templates/<app>/<model>_<action>.html` (list, detail, form)
- Новые поля с чувствительными данными шифровать через `django-cryptography-5`
- Не использовать `raw()` и `extra()` без крайней необходимости (SQL injection)

## Safety rules (важно!)
- **Миграции**: перед `makemigrations` убедиться что изменения в models.py корректны.
  Деструктивные миграции (удаление полей/таблиц) — только с явного подтверждения.
- **DEBUG**: управляется через `DJANGO_DEBUG` в `.env`. В продакшене должно быть `False`.
- **Секреты**: не выводить значения env-переменных в логи и ответы.
- **Права**: в views проверять `request.user.is_authenticated` и права доступа.
- **CSRF**: не отключать CsrfViewMiddleware, не использовать `@csrf_exempt` без причины.

## Logging
- `logs/django.log` — общие логи (INFO+)
- `logs/security.log` — события безопасности (WARNING+)
- Логгер безопасности: `logging.getLogger("security")`

## Billing архитектура
- Тарифы и лимиты — в `billing/constants.py` (не в settings.py, не в БД)
- Финансовые операции — только через `billing/services.py`: `deposit()`, `withdraw()`
- `BillingTransaction.balance_after` — снимок баланса после каждой операции (аудит)
- `metadata = JSONField` — детализация списания (breakdown по сущностям)
- `Account.is_billing_exempt = True` — привилегированный аккаунт без ограничений
- `BillingProtectedMixin` — подключать ко всем Create-views чтобы блокировать создание при долге
- Контекст-процессор `billing_account` доступен во всех шаблонах как `{{ billing_account }}`
- Cron: `charge_daily` запускать ежедневно (инструкция в `docs/cron.md` или отдельно)

## accounts: сессии и роли
- `SessionActivityMiddleware` — обновляет `last_activity` не чаще 1 раза в 5 минут
- Сигналы `user_logged_in` / `user_logged_out` в `accounts/signals.py` — управляют `UserSession`
- Лимит сессий: 3 на пользователя (`MAX_SESSIONS_PER_USER` в `billing/constants.py`); превышение логируется как `suspicious_activity`, вход не блокируется
- Роли: `owner`, `admin`, `dispatcher`, `logist` — хранятся в `UserProfile.role`

## Integration: Petrolplus
- OAuth2/Keycloak авторизация
- Код в `integrations/`
- Таймаут: `PETROLPLUS_TIMEOUT` (default 15s)

## What Claude should do by default
- Перед изменением файла — прочитать его
- Предупреждать о деструктивных операциях с БД
- Бизнес-логику размещать в services.py
- Не коммитить автоматически — только по явной просьбе
- Указывать на потенциальные уязвимости (XSS, SQL injection, IDOR, открытые views)
