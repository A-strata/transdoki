# План: настраиваемые бизнес-валидации формы рейса

> Статус: **запланировано**, не реализовано.
> Дата: 2026-03-30

## Контекст

Сейчас ряд валидаций формы рейса жёстко закодирован в `trips/validators.py`. Некоторые из них — не универсальные правила, а бизнес-предпочтения, которые у разных компаний могут отличаться. Например, требование прицепа для тягача: технически логично, но перевозчику не всегда сообщают детали о составе ТС на момент создания рейса.

### Кандидаты на настройку

| Валидатор | Функция | Почему спорен |
|---|---|---|
| `validate_trailer_for_truck` | Тягач → прицеп обязателен | Иногда данные о прицепе появляются позже |
| `validate_vehicles_belong_to_carrier` | ТС должны принадлежать перевозчику | Аренда, субподряд — владелец ≠ перевозчик |
| `validate_our_company_participation` | Своя фирма должна быть участником | Ведение чужих рейсов «для учёта» |

Остальные валидаторы (`validate_unique_trip_number_and_date`, `validate_client_cannot_be_carrier`, `validate_costs_by_our_company_role`) — не кандидаты: они защищают от ошибок данных, а не реализуют бизнес-предпочтения.

## Решение

### 1. Модель настроек аккаунта

Добавить в `accounts` (или отдельное приложение `settings`) модель с булевыми флагами:

```python
class AccountSettings(models.Model):
    account = models.OneToOneField(Account, on_delete=models.CASCADE, related_name="settings")

    # Валидации формы рейса
    validate_trailer_required = models.BooleanField(
        default=True,
        verbose_name="Требовать прицеп для седельного тягача",
    )
    validate_vehicles_belong_to_carrier = models.BooleanField(
        default=True,
        verbose_name="Проверять принадлежность ТС перевозчику",
    )
    validate_own_company_participation = models.BooleanField(
        default=True,
        verbose_name="Требовать участие своей компании в рейсе",
    )
```

Создаётся автоматически через сигнал `post_save` при создании `Account`.

### 2. Форма рейса читает настройки

В `TripForm.clean()` валидаторы вызываются условно:

```python
settings = self.user.profile.account.settings

if settings.validate_trailer_required:
    validate_trailer_for_truck(truck=..., trailer=...)

if settings.validate_vehicles_belong_to_carrier:
    validate_vehicles_belong_to_carrier(truck=..., trailer=..., carrier=...)

if settings.validate_own_company_participation:
    validate_our_company_participation(client=..., carrier=..., ...)
```

### 3. UI в личном кабинете

Новая страница «Настройки валидации» (раздел настроек аккаунта). Доступна только `owner` и `admin`.

Каждая настройка — чекбокс с пояснением, зачем правило существует и когда его стоит отключать.

## Миграция

1. Создать модель `AccountSettings` с миграцией
2. Сигнал `post_save` на `Account` — создаёт `AccountSettings` с дефолтами
3. Дата-миграция — создать `AccountSettings` для уже существующих аккаунтов
4. Обновить `TripForm.clean()`
5. Добавить view и шаблон страницы настроек

## Замечания

- Дефолты всех флагов — `True` (поведение не меняется для существующих аккаунтов после миграции)
- При добавлении новых спорных валидаторов в будущем — сразу добавлять флаг в `AccountSettings`
