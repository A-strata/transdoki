# transdoki — Django Project Guide for Claude

## Project overview
Transport document management system (путевые листы, рейсы, транспортные средства).
Production URL: transdoki.ru

## Stack
- Python 3.12, Django 5.2
- SQLite (dev) — db.sqlite3 в корне
- PostgreSQL 17 (production)
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

### Инфраструктурный слой (transdoki/)
```
transdoki/
  models.py       # UserOwnedModel, TenantManager — базовые классы мультитенантности
  views.py        # UserOwnedListView — единый базовый ListView с tenant-фильтрацией
  tenancy.py      # get_request_account() — извлечение account из request
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
- Списковые страницы с поиском/сортировкой — через Partial HTML over Fetch (partial-шаблон + `X-Requested-With` в view + fetch в JS). Подробности в `docs/ui-guide.md` раздел 14.
- При изменении объекта — проставлять `updated_by = request.user` (в `form_valid`, `post`, FBV). В `save(update_fields=[...])` добавлять `"updated_by"` в список полей.
- Системные изменения (management commands, signals, Celery tasks) — `updated_by=None` осознанно.

## Safety rules (важно!)
- **Миграции**: перед `makemigrations` убедиться что изменения в models.py корректны.
  Деструктивные миграции (удаление полей/таблиц) — только с явного подтверждения.
- **Tenant-изоляция**: любой новый view с `UserOwnedModel`-моделью обязан фильтровать по account (см. раздел «Мультитенантность»). Автотест `tests/test_tenant_isolation.py` ловит пропуски в CBV.
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

## Мультитенантность

Все доменные модели (Organization, Person, Vehicle, Trip, Waybill и др.) наследуют `UserOwnedModel` из `transdoki/models.py`.

### UserOwnedModel — поля
| Поле | Назначение |
|------|-----------|
| `account` | FK → Account (tenant). `on_delete=PROTECT` |
| `created_by` | FK → User. Кто создал. `on_delete=SET_NULL` |
| `updated_by` | FK → User. Кто последним изменил. `on_delete=SET_NULL, related_name="+"` |
| `created_at` | Автодата создания |
| `updated_at` | Автодата изменения |

### TenantManager
Все модели-наследники получают `objects = TenantManager()` с методом `for_account(account)`:
```python
# Правильно:
Organization.objects.for_account(account).filter(is_own_company=True)

# Неправильно (обходит менеджер):
Organization.objects.filter(account=account, is_own_company=True)
```

### Правила для новых views
- **ListView**: наследовать `UserOwnedListView` из `transdoki/views.py` (tenant-фильтрация + пагинация встроены)
- **DetailView / UpdateView / DeleteView**: переопределить `get_queryset` с `.for_account()`
- **CreateView**: в `form_valid` / `post` проставить `form.instance.created_by` и `form.instance.account`
- **FBV**: использовать `Model.objects.for_account(get_request_account(request))`
- **Автотест**: `tests/test_tenant_isolation.py` проверяет все CBV автоматически — забытый фильтр не пройдёт

## accounts: сессии и роли
- `SessionActivityMiddleware` — обновляет `last_activity` не чаще 1 раза в 5 минут
- Сигналы `user_logged_in` / `user_logged_out` в `accounts/signals.py` — управляют `UserSession`
- Лимит сессий: 3 на пользователя (`MAX_SESSIONS_PER_USER` в `billing/constants.py`); превышение логируется как `suspicious_activity`, вход не блокируется
- Роли: `owner`, `admin`, `dispatcher`, `logist` — хранятся в `UserProfile.role`

## Production server

- **Автодеплой**: push в `main` → сервер сам делает git pull
- **Папка проекта**: `~/projects/transdoki` (пользователь deploy)
- **Systemd-сервис**: `transdoki.service`
- **Логи приложения**: `~/projects/transdoki/logs/django.log` и `security.log`
- **Переменные окружения**: `~/projects/transdoki/.env`
- **SSH**: два пользователя — `deploy` (файлы, логи) и `root` (systemctl); SSH-ключ и IP хранятся локально в памяти Claude
- **Python/venv**: poetry не в PATH у deploy, использовать venv напрямую:
  ```bash
  ~/projects/transdoki/.venv/bin/python manage.py <cmd>
  # или: source ~/projects/transdoki/.venv/bin/activate
  ```

Типичный рабочий цикл:
```bash
# push в main → автодеплой
# перезапустить сервис (нужно при изменении .env или зависимостей):
ssh root@<server> "systemctl restart transdoki"
# логи:
ssh deploy@<server> "tail -f ~/projects/transdoki/logs/django.log"
```

## Integration: Petrolplus
- OAuth2/Keycloak авторизация
- Код в `integrations/`
- Таймаут: `PETROLPLUS_TIMEOUT` (default 15s)

## UI conventions (критические правила)
- CSS-кнопки: `.tms-btn` + модификатор (`-primary`, `-secondary`, `-light`, `-fix`, `-add`)
- Одна `.tms-btn-primary` на страницу, остальные — secondary
- Flash-сообщения: только `messages.success/error/warning()` в view; НЕ дублировать `{% if messages %}` в шаблонах
- Инлайн `<style>` и `<script>` запрещены — только внешние файлы через `{% static %}`
- Django-данные в JS — через `data-`атрибуты, не инлайн-скрипты
- Формы: `.form-card` > `.section` > `.fields-grid` > `.field`
- Disabled-кнопки: нативный атрибут `disabled`, не CSS-класс
- Полный справочник: `docs/ui-guide.md`

## What Claude should do by default
- Перед изменением файла — прочитать его
- Предупреждать о деструктивных операциях с БД
- Бизнес-логику размещать в services.py
- Не коммитить автоматически — только по явной просьбе
- Указывать на потенциальные уязвимости (XSS, SQL injection, IDOR, открытые views)
