# Архитектурный ревью биллинга transdoki

Дата: 2026-04-19
Объём кода: `billing/` ≈ 10 сервисных файлов + 3 команды + 6 вьюх + 8 миграций + 2300+ строк тестов.

---

## TL;DR

Архитектура в целом зрелая и соответствует современным практикам SaaS-биллинга: слоистая структура, атомарные транзакции с блокировками, идемпотентность по нескольким уровням, timing-safe проверка HMAC, разделение «балансной» и «подписочной» моделей. Есть набор реальных проблем — одна из которых потенциально финансовая (race condition в `handle_pay_webhook`) — и накопившийся технический долг от сосуществования двух биллинговых моделей (старой посуточной и новой месячной).

Общая оценка: **7.5/10** — хороший фундамент, нужна целевая дошлифовка.

---

## 1. Сильные стороны

### 1.1 Слоистая архитектура services/
Разделение `billing/services/` на `balance`, `charging`, `plan_change`, `modules`, `usage`, `limits`, `lifecycle`, `history` — чистое SRP. Каждый модуль имеет понятную зону ответственности, views остаются тонкими.

### 1.2 Атомарность и изоляция
`withdraw` / `deposit` / `_charge_balance` выполняются внутри `transaction.atomic()` + `select_for_update()` на `Account`. Это правильная защита от потерянных обновлений при параллельных операциях (webhook CloudPayments + ручное списание и т. п.).

### 1.3 Многоуровневая идемпотентность `charge_monthly`
- Advisory lock (`pg_try_advisory_lock`) — защита от параллельного запуска cron.
- `UniqueConstraint(account, period_start)` на `BillingPeriod` — защита на уровне БД.
- Дополнительная предварительная проверка `BillingPeriod.objects.filter(...).exists()` + `try/except IntegrityError` — защита на прикладном уровне.
- `exempt`-аккаунты пропускаются без продвижения периода.

Это учебник по идемпотентному биллингу. Отдельно радует комментарий про «подстраховку к advisory lock на случай SQLite или ручного запуска».

### 1.4 Безопасность CloudPayments-интеграции
- HMAC-SHA256 + base64, сверка через `hmac.compare_digest` (timing-safe).
- Сверка `InvoiceId` + `Amount` в `handle_check_webhook` — защита от подмены суммы на клиенте.
- Test-mode платежи отвергаются в production (конфигурируемо через `CLOUDPAYMENTS_ALLOW_TEST_MODE`).
- `request.body` читается ДО `request.POST` (иначе Django съедает bytes и HMAC не рассчитать) — тонкий момент, правильно задокументирован.
- Осмысленное использование кодов CP: `0` / `10` / `20` — clear differentiation между «принято», «отвергнуть навсегда», «повторить позже».

### 1.5 Аудит-трейл
- `BillingTransaction.balance_after` — снимок баланса после каждой операции. Позволяет реконструировать баланс постранично, ловить дрейф.
- `BillingPeriod.modules_snapshot` — исторический снимок подключённых модулей. Даже если модуль потом отключат — отчёт за прошлый период корректен.
- `PaymentOrder.cp_data` (JSONField) с полями из webhook — аудит со всеми деталями карты (маска), IP, банка-эмитента.

### 1.6 Корректная обработка периодов
- `_add_months` вручную реализован с учётом коротких месяцев (31 марта + 1 = 30 апреля, а не 1 мая).
- Рейс относится к месяцу по `created_at`, а не по 24-часовому окну подтверждения (§3.3 ТЗ).
- Использование `Trip.all_objects` вместо `Trip.objects` для учёта soft-deleted рейсов за пределами 24-часового окна.

### 1.7 Pro rata при апгрейде
Стандарт Stripe — подсчёт в целых днях, rounding вниз (клиенту начисляем не больше, чем положено). `_pro_rata` ≥ 0 и защищён от деления на ноль.

### 1.8 Grandfather-mode на даунгрейде
`schedule_downgrade` не блокирует переход, даже если новый план имеет меньший лимит, чем текущее использование. Возвращаются warnings для UI. Существующие сущности остаются, новые создавать нельзя. Это правильная UX-модель.

### 1.9 `effective_*` properties
`Subscription.effective_monthly_price / _trip_limit / _user_limit / _organization_limit / _overage_price` — чистый способ переопределения параметров для Corporate через `custom_*` поля. Вызывающий код не знает о существовании кастомизации.

### 1.10 Разделение логгеров
`logger = logging.getLogger("security")` для `deposit` / `withdraw` / CloudPayments HMAC / подозрительных событий + `logging.getLogger("billing")` для жизненного цикла подписки. Даёт гибкость алертинга.

### 1.11 Тестовое покрытие
2300+ строк тестов, явно структурированных по сценариям ТЗ (§12.1 ТЗ в `test_charge_monthly.py`). Тесты покрывают граничные кейсы (рейс 31.01 23:55, custom limit None, dry-run идемпотентность, активные модули, scheduled_plan и т. д.).

### 1.12 Freemium-миграция
Миграция `0005_seed_plans_and_subscriptions` создаёт Subscription на Free для всех существующих аккаунтов. После этого `Account → Subscription (OneToOne)` становится инвариантом, на который опирается остальной код. Signal `auto_create_free_subscription` поддерживает инвариант для новых аккаунтов.

---

## 2. Серьёзные проблемы

### 2.1 Race condition в `handle_pay_webhook` — потенциальный финансовый риск

Код явно отказывается от `select_for_update` на `PaymentOrder`:

```python
# billing/cloudpayments.py:229-232
# Не используем select_for_update: соединение до внешней БД может
# оказаться в autocommit-режиме в момент вызова (после сетевого сброса),
# что вызывает TransactionManagementError даже внутри atomic().
# Идемпотентность обеспечена transaction.atomic() + проверкой статуса ниже.
```

Это логически некорректно. При **параллельных** webhook-ах от CloudPayments (ретрай пересекается с первичной доставкой — CP может это сделать) оба запроса при READ COMMITTED прочитают `status=pending`, оба пройдут проверку, оба вызовут `deposit()` и удвоят зачисление. Окончательный `UPDATE status=paid` идемпотентен, но деньги уже дважды начислены.

**Что делать:**
- Вернуть `select_for_update()` и разобраться с `TransactionManagementError` (скорее всего виноват был другой паттерн — реюз коннекшна в autocommit после сбоя). Современный Django + PostgreSQL этот вопрос решает корректно внутри `atomic()`.
- Либо использовать уникальный частичный индекс `UNIQUE (order_id) WHERE status = 'paid'` и `ON CONFLICT DO NOTHING` на бриджевой транзакции.
- Либо `pg_advisory_xact_lock` по `order_id.int` (самое простое и переносимое).

В любом случае комментарий «идемпотентность обеспечена transaction.atomic() + проверкой статуса» — ложный в текущей реализации.

### 2.2 Два параллельных биллинга: `charge_daily` и `charge_monthly`

Из `billing/constants.py`:
```python
DAILY_RATE_ORG = Decimal("15.00")
DAILY_RATE_VEHICLE = Decimal("10.00")
DAILY_RATE_USER = Decimal("5.00")
```

Из `billing/management/commands/charge_daily.py`:
```python
accounts = Account.objects.filter(is_active=True, is_billing_exempt=False)
for account in accounts:
    cost, breakdown = billing_services.get_daily_cost(account)
    billing_services.withdraw(account=account, amount=cost, ...)
```

Одновременно `charge_monthly` уже списывает по подписочной модели (Plan × effective_monthly_price). Если крон сейчас зовёт и `charge_daily`, и `charge_monthly` — аккаунт платит дважды: посуточно за ресурсы и ежемесячно за подписку.

Это **самая большая архитектурная проблема** — половина миграции из v1 в v2 оставлена в коде. В `billing/mixins.py` даже записано: «Старый BillingProtectedMixin удалён: проверка «balance > credit_limit» заменена на per-entity-лимиты в подписочной модели». То есть решение принято. Но `charge_daily.py` всё ещё в `management/commands/`.

**Что делать:**
- Удалить `charge_daily.py` + `get_daily_cost` + `DAILY_RATE_*` + `free_orgs/vehicles/users` на `Account` + `cached_daily_cost` — если задача уже закрыта.
- Или, если `charge_daily` нужен только для UI-виджета «суточная стоимость» — выделить в отдельный сервис, но не списывать с баланса.
- В CLAUDE.md проекта оставлен дословный след старой модели: «`BillingProtectedMixin` — подключать ко всем Create-views чтобы блокировать создание при долге». Этот миксин удалён (замещён `LimitCheckMixin`). Документация и код разошлись.

### 2.3 Неполный жизненный цикл past_due

`_charge_one_subscription` при нехватке баланса создаёт `BillingPeriod.status=invoiced` и оставляет «висящий долг». Комментарий честно говорит:

```
Погашение — отдельным действием клиента в ЛК (итерация 5 UI):
клиент пополняет баланс и нажимает «оплатить задолженность».
Автоматического списания после восстановления баланса НЕ делаем
```

Но в `billing/urls.py` нет endpoint-а «оплатить задолженность». В `billing/services/` нет функции вроде `pay_outstanding_debt(account)`. Клиент может пополнить баланс, но `BillingPeriod` останется `invoiced` до ручного вмешательства. 14 дней grace, и он в `suspended`.

В context-процессоре `billing_banner` debt_amount считается, в UI показывается — но кнопки действия нет.

**Что делать:** дописать `services/lifecycle.py::pay_outstanding_periods(account)` + endpoint + кнопку на странице «Мой тариф». Иначе весь past_due-сценарий висит.

### 2.4 Нет `select_for_update` на PaymentOrder — двойной успех `handle_pay_webhook`

Связано с 2.1, но отдельная проблема: commentарий в коде объясняет отказ от select_for_update тем, что раньше был TransactionManagementError. Это звучит как лечение симптома, а не причины. В современном Django проблема реюза autocommit-соединения в `atomic()` обычно говорит о том, что:

- кто-то сверху делает `connection.close()` в middleware;
- либо используется `connection.ensure_connection()` в неподходящий момент;
- либо проблема вообще в старой версии psycopg.

Это стоит диагностировать и лечить, а не обходить отсутствием lock'а. Важно: pytest-ы этот кейс не ловят, потому что SQLite параллельность не воспроизводит.

---

## 3. Проблемы среднего уровня

### 3.1 Дублирование `_charge_balance`

`charging.py::_charge_balance` и `plan_change.py::_charge_balance` — почти идентичны. Второй сам пишет:
```python
# ВАЖНО: дублирует логику из charging._charge_balance. Когда накопится
# третий case, вынести в shared helper...
```

Третий case уже есть: `modules.py` импортирует `_charge_balance` из `plan_change.py`. То есть рефакторинг созрел. Вынести в `balance.py::_charge_balance_locked(account, amount, kind, *, description, billing_period=None)` — одна точка входа для всех «списаний, уже внутри transaction.atomic()».

### 3.2 `build_history` грузит всё в память

В `services/history.py`:
```python
events: list[HistoryEvent] = [
    _transaction_to_event(tx) for tx in tx_qs
] + [
    _period_to_event(bp, plan_names) for bp in bp_qs
]
events.sort(key=lambda e: e.date, reverse=True)
```

А потом в view:
```python
paginator = Paginator(events, self.paginate_by)
```

То есть все транзакции + все периоды аккаунта грузятся в Python **каждый раз при открытии страницы**, чтобы отдать 50 записей одной страницы. Для клиента с 2-летней историей это ~500+ объектов ORM на каждый GET.

У сервиса в docstring честно сказано: «Если упрёмся — перейти на SQL UNION». На текущем объёме может и не упрётесь, но лучше сразу сделать:
- `date_from` по умолчанию = 90 дней назад, явный UI-выбор дальше;
- либо курсорная пагинация по `created_at`;
- либо два отдельных пагинированных QuerySet'а + склейка по времени через `heapq.merge` на одной странице.

### 3.3 `InsufficientFunds` — текстовое исключение, UI пересчитывает сумму

В `views.py::subscription_upgrade`:
```python
except InsufficientFunds as exc:
    required = _estimate_upgrade_price(account, plan_code)
```

То есть `upgrade_plan` выкинул исключение с информацией о сумме в строке, а view вынужден повторить расчёт, чтобы отдать JSON-ответу поле `required`. Это запах: двойной расчёт pro rata в двух местах. Решение — структурированное исключение:

```python
class InsufficientFunds(BillingError):
    def __init__(self, required: Decimal, available: Decimal, *, message: str = None):
        self.required = required
        self.available = available
        super().__init__(message or f"Требуется {required} ₽, доступно {available} ₽")
```

Тогда view достанет `exc.required` вместо `_estimate_upgrade_price`.

### 3.4 `AVAILABLE_MODULES` vs `Module` в БД — два источника правды

В `constants.py`:
```python
AVAILABLE_MODULES = {"contracts": "Договоры"}
```

А в БД — `Module` таблица с теми же кодами. При рассинхроне один из источников даст неправильный ответ. Поскольку есть таблица, константа должна быть удалена — либо наоборот, таблицы не нужно и всё читается из `constants`.

### 3.5 Хардкод 14-дневного grace

`PAST_DUE_GRACE_DAYS = 14` в `services/lifecycle.py`. Для Corporate-аккаунтов часто нужно индивидуально (30 дней и т. п.). Положите в `constants.py` как дефолт + `Subscription.grace_days` nullable override.

### 3.6 `auto_create_free_subscription` тихо пропускает при отсутствии Free-плана

```python
try:
    free_plan = Plan.objects.get(code="free")
except Plan.DoesNotExist:
    logger.warning(...)
    return
```

Если Free-план почему-то удалили в админке — новые аккаунты создаются без подписки и в тот же миг ломается `can_create_*`. Нужно:
- либо `@receiver(class_prepared)` / system check, валидирующий наличие `Plan(code="free")` на старте приложения;
- либо `Plan.objects.get_or_create(code="free", defaults=...)` прямо в сигнале.

### 3.7 `scheduled_plan` — только для даунгрейда

Осмысленное ограничение (апгрейд — сразу с pro rata), но в будущем может понадобиться «запланировать переход на более дорогой план с 1-го числа следующего месяца». Модель уже поддерживает (FK), нужна только `schedule_upgrade_at_period_end()` service. Помечу как enhancement, не bug.

### 3.8 `advisory_lock` в `process_past_due` — своя копия логики

В `charging.py` функция `advisory_lock` — context manager с красивой API. В `process_past_due.py` — inline `with connection.cursor()`. Два разных стиля для одной операции. Вынести `advisory_lock` в отдельный `billing/services/locks.py` (или оставить в `charging.py` и переиспользовать).

### 3.9 `contracts` модуль с ценой 0 ₽

Миграция 0005 создаёт модуль `contracts` с `monthly_price=0.00`. При этом:
```python
if pro_rata > 0:
    _charge_balance(...)
```
— то есть на ноль не списываем. OK. Но в UI `activate_module` показывает «требуется 0 ₽, подключаем бесплатно» — это странный UX. Явное решение: либо плата не 0, либо модуль bundle-включён в тариф без отдельной активации.

---

## 4. Мелкие замечания

### 4.1 Корпоративный контакт захардкожен
```python
ctx["corporate_contact_email"] = "a.astakhin@gmail.com"
```
В `views.py::SubscriptionView`. Лучше `settings.CORPORATE_CONTACT_EMAIL`.

### 4.2 `_add_months` vs `dateutil.relativedelta`
Оправдано в комментарии: «python-dateutil не установлен». Но для `docxtpl` обычно подтягивается и это уже полезная зависимость. Впрочем, свой код проще проверить тестами.

### 4.3 `Kind.REFUND` есть, сервиса нет
`BillingTransaction.Kind.REFUND` определён, но нет функции `refund(account, amount, reason)`. Рефанды через Django admin — запись в БД минуя инварианты (проверка знака, сопоставление с оригинальной транзакцией и т. п.). Это риск ручной ошибки.

### 4.4 Bulk update в `process_past_due_accounts`
Итерация по QS + `save()` на каждом — N+1 пишущих запросов. Лучше:
```python
qs.update(status=Subscription.Status.SUSPENDED, updated_at=timezone.now())
```
с предварительным `list(qs.values_list("account_id", "past_due_since"))` для лога. Для текущего размера не критично, но при 10k аккаунтов ощутимо.

### 4.5 `charge_daily` считает баланс через `account.balance - cost`
```python
logger.info(
    "charge_daily: account_id=%s charged=%s balance_after=%s",
    account.pk, cost, account.balance - cost,  # приближённо
)
```
Правильный баланс уже есть в `tx.balance_after`. Или лог можно перенести внутрь `withdraw()`, где знают точное значение.

### 4.6 Нет теста на race в webhook
Учитывая 2.1, хорошо бы юнит-тест через `threading.Barrier` или `@override_settings(DATABASES=postgresql)` + `@tag("concurrent")`.

### 4.7 `balance_after` не сверяется с реальным `account.balance`
Если `balance_after` начнёт дрейфовать от `account.balance` (например, из-за бага или прямого UPDATE в БД) — никто не заметит. Аудит-команда `reconcile_balance` не повредила бы:
```python
sum_of_ops = (
    sum(deposits) - sum(withdraws)
) == expected_balance
```
и алерт при расхождении.

### 4.8 `billing_banner` — запрос в БД на каждом request
```python
last_invoiced = BillingPeriod.objects.filter(...).first()
```
Для past_due-клиентов на каждой странице выполняется дополнительный запрос. Кешировать на request или хотя бы `select_related`-подход не помогает (BillingPeriod берётся отдельно). Добавить `@cached_property` на объекте `billing_banner` dict или кеш на 60 секунд через `cache.get_or_set`.

### 4.9 `Subscription.BillingCycle.YEARLY` определён, но нигде не используется
Годовые подписки не реализованы: `_advance_period` всегда делает `+1 month`, `effective_monthly_price` единственное поле цены. Либо удалить choice до его реализации, либо дореализовать с `_add_years`.

### 4.10 `_period_to_event` склеивает описание через " • "
Минор, но разделитель визуальный — лучше вынести в шаблон и передавать структурированный массив полей.

---

## 5. Что хорошо для начала, но со временем станет узким местом

### 5.1 Объединение истории в Python
См. 3.2. Пока данные помещаются в RAM — OK. Ориентир: 100k транзакций на аккаунт = ~30MB в памяти на один GET. Это не порог «завтра».

### 5.2 Advisory lock на один `charge_monthly`
Текущая реализация — один `_LOCK_KEY` на всех. При росте клиентов (>10k) `charge_monthly` будет идти минуты, крон может засечь таймаут. Решение — шардировать по `account_id % N` с N lock-ами.

### 5.3 Синхронный CloudPayments webhook
`handle_pay_webhook` делает запись в 3 таблицы внутри `atomic()`, потом логирует и возвращает `{"code": 0}`. Если зависла запись в `BillingTransaction` (например, триггер в будущем) — CP не получит ответ за 30 сек и повторит. Долгосрочно нужен outbox pattern: webhook принимает → пишет в `inbox` → background-воркер обрабатывает.

### 5.4 Нет событий (event bus)
Оплата подписки должна триггерить: email-уведомление, отправку чека в ФНС (для ОФД), обновление CRM, нотификацию владельцу. Сейчас эти места помечены `# TODO`. Когда их станет больше 2-3, пригодится `django-post-office` / Celery + outbox.

---

## 6. Вопросы, на которые стоит ответить продукту

1. **Что делать с `charge_daily`?** Выпилить полностью или оставить как «информационный» счётчик?
2. **Как клиент платит задолженность?** Нужен endpoint + UI, иначе past_due-флоу мёртвый.
3. **Модуль `contracts` платный или бесплатный?** Сейчас `price=0`, но UI/активация заточены под платный.
4. **Нужны ли годовые подписки?** Если нет — удалить `BillingCycle.YEARLY`.
5. **Как обрабатываются рефанды?** Только через admin? Юридически фиксируется где?
6. **Политика grace — 14 дней для всех планов или Corporate иначе?**

---

## 7. Приоритизированный чек-лист исправлений

**P0 — финансовый риск:**
1. Починить race в `handle_pay_webhook` (вернуть `select_for_update` или ввести advisory lock per-order_id).
2. Определиться с `charge_daily` — удалить или пересмотреть, чтобы не удваивать списания с `charge_monthly`.

**P1 — функциональные дыры:**
3. Добавить `pay_outstanding_debt(account)` + endpoint + кнопку в UI.
4. Добавить управляемый `refund(...)` service.
5. Добавить reconcile-команду `reconcile_balance` с алертом.

**P2 — технический долг:**
6. Вынести `_charge_balance` в `balance.py`.
7. Структурировать `InsufficientFunds` с полями `required`/`available`.
8. Убрать `AVAILABLE_MODULES` (оставить только Module-таблицу).
9. Переписать `build_history` с дефолтным `date_from` и SQL-UNION / курсором, когда объём вырастет.
10. Привести документацию CLAUDE.md к коду (`BillingProtectedMixin` удалён, записать это).

**P3 — nice-to-have:**
11. Общий context-manager `advisory_lock` в `billing/services/locks.py`.
12. System check на наличие `Plan(code="free")` при старте.
13. Bulk-update в `process_past_due_accounts`.
14. Кешировать `billing_banner` на request / 60 сек.
15. Структурированные поля events в `_period_to_event`.

---

## 8. Итог

Подсистема спроектирована человеком, понимающим SaaS-биллинг: правильный набор инвариантов (идемпотентность, атомарность, snapshot'ы, grandfather, pro rata), аккуратная интеграция с внешним платёжным провайдером, защита от timing-attack. Основные риски — в местах, где старое (суточные списания) ещё не удалено, и в webhook-идемпотентности, которая полагается на комментарий, а не на замок. Если закрыть P0+P1 за одну итерацию — биллинг становится production-grade с хорошим запасом.
