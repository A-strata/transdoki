# Бриф: actionable-алерт о балансе (5-state model)

**Версия:** 1.0
**Дата:** 20.04.2026
**Автор:** продуктовый дизайн
**Исполнитель:** Claude Code
**Связано:** хотфикс `billing/context_processors.py` (`×3 → ×1`) — уже применён; `billing/services/` (charge_daily, subscription status lifecycle); `templates/base.html` (бейдж + баннер); `accounts/templates/accounts/cabinet.html` (inline-alert)

---

## Цель

Заменить текущий бинарный алерт «низкий баланс / нет алерта» на 5-уровневую stateful-модель, где каждое состояние несёт **конкретную сумму**, **конкретную дату** и **одно ясное действие** (или отсутствие действия, если всё ок).

Пользователь в любой момент должен понимать: «что с моим биллингом прямо сейчас, когда следующее списание и сколько оно будет, что от меня ждут».

## Проблема (после хотфикса `×3 → ×1`)

Хотфикс снял ложный стресс, но система осталась однорежимной: есть один флаг `balance < effective_monthly_price` → показываем тот же алерт «Пополните баланс». Что не решено:

1. **Нет суммы и даты.** Алерт говорит «пополните», но не говорит **сколько** и **когда** иначе. Пользователь вынужден идти в биллинг и считать сам.
2. **Нет различия «впритык» vs «уже нет денег».** Баланс 100₽ при месячной цене 990₽ визуально неотличим от баланса 0₽.
3. **`past_due` и `suspended` сейчас рендерятся через отдельный `billing_banner`** — это правильно, но визуально не связано с бейджем и inline-алертом в ЛК. Три канала оповещения живут отдельно.
4. **После хотфикса пропал upcoming-режим.** Пользователь с балансом ровно на одно списание не увидит предупреждения — узнает постфактум, когда `charge_daily` переведёт в `past_due`.
5. **Кнопка «Пополнить» ведёт на форму без предзаполненной суммы.** Пользователь сам вводит, часто на глаз.

## 5-state model

| # | State | Условие | Канал | Тон | Действие |
|---|---|---|---|---|---|
| 1 | **ok** | `balance ≥ next_charge_amount × 2` | — | — | — |
| 2 | **upcoming** | `next_charge_amount ≤ balance < next_charge_amount × 2` | бейдж `.is-info` в навбаре | спокойный | «Следующее списание {date}: {amount} ₽. После него останется {balance − amount} ₽.» |
| 3 | **urgent** | `0 ≤ balance < next_charge_amount` | бейдж `.is-warn` + inline-alert в ЛК | предупреждающий | «{date} спишется {amount} ₽, на балансе {balance} ₽. Пополните минимум на {amount − balance} ₽, иначе тариф уйдёт в past_due.» + кнопка «Пополнить на {amount − balance} ₽» |
| 4 | **past_due** | `subscription.status == "past_due"` | бейдж `.is-danger` + inline-alert + глобальный баннер | тревожный | «Оплата не прошла {failed_at}. Тариф остановится {suspended_at}, если не пополнить на {amount_due} ₽.» + кнопка «Пополнить на {amount_due} ₽» |
| 5 | **suspended** | `subscription.status == "suspended"` | бейдж `.is-danger` + блокировка create-операций | блокирующий | «Тариф приостановлен. Доступ к созданию рейсов/путевых листов/сотрудников заблокирован. Пополните на {amount_due} ₽, чтобы возобновить.» + кнопка «Пополнить на {amount_due} ₽» |

**Ключевое различие с текущим кодом:** у состояний 2–5 **всегда есть сумма** (`next_charge_amount` или `amount_due`) и **всегда есть дата** (`next_charge_date`, `failed_at`, `suspended_at`). Не «пополните баланс», а «пополните на 347 ₽, иначе 15 мая тариф уйдёт в past_due».

Exempt-аккаунты (`is_billing_exempt=True`) и free tier (`subscription.plan_id is None`) — всегда `ok`, никаких алертов.

## Решение

### 1. Сервис `billing/services/balance_state.py` (новый файл)

Единая точка истины — функция `get_balance_state(account) -> BalanceState`:

```python
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

StateCode = Literal["ok", "upcoming", "urgent", "past_due", "suspended"]

@dataclass(frozen=True)
class BalanceState:
    code: StateCode
    balance: Decimal
    next_charge_amount: Decimal | None       # сколько будет списано в ближайшее списание
    next_charge_date: date | None            # когда
    amount_to_topup: Decimal | None          # рекомендованная сумма пополнения (для urgent/past_due/suspended)
    failed_at: date | None                   # past_due only
    suspended_at: date | None                # past_due only — когда уйдёт в suspended
```

Логика:
- Exempt / нет подписки / нет плана → `ok` со всеми полями `None`.
- Иначе считаем `next_charge_amount = subscription.effective_monthly_price`, `next_charge_date = subscription.current_period_end + 1 day` (или аналогичное поле, уточнить в модели).
- Если `status == "past_due"` / `"suspended"` — маппим напрямую, заполняем `failed_at`, `suspended_at` из `subscription.past_due_since + PAST_DUE_GRACE_DAYS`.
- Для активных — `upcoming` / `urgent` / `ok` по порогам из таблицы выше.

**Важно:** никакой бизнес-логики в context-processor'е — только вызов сервиса и раскладка в шаблонные переменные. Легко покрывается unit-тестами без request-контекста.

### 2. Context-processor `billing/context_processors.py` — расширение

Заменить текущий плоский набор (`billing_warn_threshold`, `billing_banner`) на единый объект:

```python
def billing_alert(request):
    if not request.user.is_authenticated:
        return {}
    account = get_request_account(request)
    if account is None:
        return {}
    state = get_balance_state(account)
    return {
        "billing_alert": state,                # основной объект
        "billing_alert_code": state.code,      # для шаблонных {% if billing_alert_code == "urgent" %}
    }
```

Старые ключи (`billing_warn_threshold`, `billing_banner`) удалить или пометить deprecated — они становятся частными случаями `billing_alert`.

### 3. Бейдж в навбаре `templates/base.html`

Сейчас (после хотфикса) — `{% if billing_warn_threshold and account.balance < billing_warn_threshold %}`.

Станет:

```django
{% if billing_alert_code == "upcoming" %}
    <span class="lk-balance-badge is-info" title="Следующее списание {{ billing_alert.next_charge_date|date:'j E' }}">
        {{ account.balance|floatformat:0 }} ₽
    </span>
{% elif billing_alert_code == "urgent" %}
    <span class="lk-balance-badge is-warn" title="Не хватит на {{ billing_alert.next_charge_date|date:'j E' }}">
        {{ account.balance|floatformat:0 }} ₽
    </span>
{% elif billing_alert_code in "past_due,suspended" %}
    <span class="lk-balance-badge is-danger">
        {{ account.balance|floatformat:0 }} ₽
    </span>
{% else %}
    <span class="lk-balance-badge">{{ account.balance|floatformat:0 }} ₽</span>
{% endif %}
```

Классы `is-info`/`is-warn`/`is-danger` уже есть в CSS бейджа — переиспользуем.

### 4. Inline-alert в ЛК `accounts/templates/accounts/cabinet.html`

Сейчас: один `{% if not account.is_billing_exempt and account.balance >= 0 and account.balance < billing_warn_threshold %}` с текстом «Низкий баланс».

Станет — партиал `billing/_alert_inline.html`, подключаемый в cabinet.html и в subscription.html:

```django
{% include "billing/_alert_inline.html" with alert=billing_alert %}
```

Внутри партиала — свитч по `alert.code`:
- `ok`, `None` → ничего.
- `upcoming` → мягкий info-блок с `next_charge_amount` и `next_charge_date`, без CTA.
- `urgent` → warning-блок с CTA `<a href="{% url 'billing:deposit' %}?amount={{ alert.amount_to_topup }}">Пополнить на {{ alert.amount_to_topup }} ₽</a>`.
- `past_due` → danger-блок с датой `suspended_at` и той же CTA.
- `suspended` → danger-блок + явный текст «создание новых сущностей заблокировано».

### 5. Глобальный баннер над `<main>` — оставляем для `past_due`/`suspended`

Сейчас `billing_banner` уже рендерит баннер на всех страницах при `past_due`/`suspended`. Оставляем, но переводим на тот же `billing_alert.code`:

```django
{% if billing_alert_code in "past_due,suspended" %}
    {% include "billing/_alert_banner.html" with alert=billing_alert %}
{% endif %}
```

Для `urgent` глобальный баннер **не показываем** — достаточно бейджа и inline-алерта в ЛК, иначе перекрывает все страницы.

### 6. Предзаполненная сумма в `billing:deposit`

Форма пополнения должна принимать `?amount=` в GET и подставлять в поле. Если в `billing/views.py` у `DepositView` уже есть `get_initial` — добавить туда чтение `request.GET.get("amount")` с валидацией (Decimal ≥ 0, ≤ разумного максимума типа 1 млн). Если нет — добавить.

Если у `DepositView` нет контроля над initial (например, это FormView с жёсткой формой) — остановиться, согласовать отдельным шагом.

### 7. Тесты `billing/tests/test_balance_state.py` (новый файл)

Минимум 7 unit-тестов на чистую функцию `get_balance_state`:
1. Exempt аккаунт → `ok`.
2. Без подписки / без плана → `ok`.
3. Active + balance ≥ 2× price → `ok`.
4. Active + price ≤ balance < 2× price → `upcoming`, `next_charge_amount == price`, `next_charge_date` заполнена.
5. Active + 0 ≤ balance < price → `urgent`, `amount_to_topup == price − balance`.
6. `status="past_due"` → `past_due`, `failed_at` и `suspended_at` заполнены, `amount_to_topup == price` (или `past_due_debt`, уточнить из модели).
7. `status="suspended"` → `suspended`, `amount_to_topup` заполнена.

Тесты на context-processor и шаблоны — не обязательны (чистая функция покрывает логику), но приветствуется smoke-тест на `cabinet.html` в каждом из 5 состояний.

## Файлы

| Файл | Что меняем |
|---|---|
| `billing/services/balance_state.py` | **Новый.** Dataclass `BalanceState` + функция `get_balance_state(account)`. |
| `billing/context_processors.py` | Удалить старую логику `warn_threshold` (после хотфикса осталась голая), добавить `billing_alert` + `billing_alert_code` через вызов сервиса. Старые ключи (`billing_banner`) — удалить или сделать алиасом на время перехода. |
| `billing/templates/billing/_alert_inline.html` | **Новый партиал.** Свитч по 5 состояниям. Содержимое блоков — короткий текст + опциональная CTA. |
| `billing/templates/billing/_alert_banner.html` | **Новый партиал.** Только для `past_due`/`suspended`. По сути — перенос текущего `billing_banner`-шаблона в партиал с актуальной суммой. |
| `templates/base.html` | Бейдж — switch по `billing_alert_code`. Глобальный баннер — include партиала при `past_due`/`suspended`. |
| `accounts/templates/accounts/cabinet.html` | Заменить текущий `{% if balance < warn_threshold %}…` на `{% include "billing/_alert_inline.html" %}`. |
| `billing/templates/billing/subscription.html` | Добавить тот же include в начало `{% block content %}` — пользователь на странице биллинга тоже должен видеть алерт. |
| `billing/views.py` (DepositView) | Добавить чтение `?amount=` в `get_initial`. Валидация: Decimal, ≥ 0, ≤ 1 000 000. |
| `billing/tests/test_balance_state.py` | **Новый.** 7 тестов по состояниям. |

## Acceptance criteria

1. Пользователь с `is_billing_exempt=True` — никаких бейджей цветных, никакого inline-алерта, никакого баннера. Нейтральный бейдж баланса без классов.
2. Free tier (`subscription.plan_id is None`) — то же самое: состояние `ok`, никаких алертов.
3. Active + balance ≥ 2× monthly_price — состояние `ok`, никаких алертов.
4. Active + balance между 1× и 2× monthly_price — **бейдж `.is-info`** в навбаре, inline-алерт в ЛК с текстом «Следующее списание {date}: {amount} ₽». Без CTA «пополнить». Без глобального баннера.
5. Active + balance < monthly_price — **бейдж `.is-warn`** + inline-алерт с CTA «Пополнить на {X} ₽» (где X = monthly_price − balance). Без глобального баннера.
6. `status="past_due"` — **бейдж `.is-danger`** + inline-алерт + глобальный баннер (на всех страницах). Во всех трёх каналах — одна и та же сумма пополнения и одна и та же дата `suspended_at`. CTA с `?amount=` ведёт на `deposit` с предзаполненной суммой.
7. `status="suspended"` — то же, что `past_due`, плюс в inline-алерте явно написано «создание новых сущностей заблокировано» (согласуется с `LimitCheckMixin`).
8. Клик по CTA «Пополнить на {X} ₽» открывает `/billing/deposit/` с полем суммы, **уже заполненным** значением X. Пользователю остаётся только подтвердить.
9. Все 5 состояний покрыты unit-тестами в `test_balance_state.py`. `ruff check .` и `python manage.py test billing` — зелёные.
10. Старый ключ контекста `billing_warn_threshold` удалён из всех шаблонов. `grep -rn "billing_warn_threshold" templates/ billing/` — пусто.
11. Никаких новых миграций. Никаких изменений в `charge_daily` и в lifecycle подписки — только UI-слой и чистый read-only сервис.

## Open questions (если возникнут)

1. **`subscription.current_period_end`** — это дата **конца** текущего периода, после которой происходит списание, или дата **самого списания**? Если разница больше суток, пересчитать `next_charge_date`. Не гадать — посмотреть в `billing/services/charge_daily` и `billing/models.Subscription`.
2. **`past_due_debt` / `amount_due`** — есть ли в модели отдельное поле с суммой, которую пытались списать и не смогли, или его нужно вычислять как `monthly_price − balance`? Если поле есть — использовать его. Если нет — временно `monthly_price − balance`, пометить TODO для следующей итерации.
3. **`DepositView.get_initial`** — если `DepositView` не наследует стандартный FormView, а написан вручную (например, FBV с `POST` → прямой `deposit()`), — остановиться, доложить. Добавление `?amount=` станет отдельной микрозадачей.
4. **Партиал `_alert_banner.html`** — если текущий `billing_banner` в `base.html` встроен инлайном (не включен через include), — просто переносим контент в партиал. Если уже include — заменяем контент файла.

Не принимать решения молча.

## Definition of done

- В любом из 5 состояний пользователь видит **конкретную сумму и дату** (или ничего, если `ok`).
- CTA «Пополнить на {X} ₽» везде одинаковая, ведёт на форму с предзаполненной суммой.
- Три канала (бейдж / inline-алерт / глобальный баннер) согласованы между собой: показывают одну и ту же информацию на одном и том же состоянии.
- Логика состояний — в чистом сервисе, покрыта unit-тестами.
- `billing_warn_threshold` как понятие удалён — его заменил stateful `billing_alert`.
- Никаких регрессий: active+богатый аккаунт по-прежнему не видит никаких предупреждений; past_due/suspended по-прежнему блокируют create-операции через `LimitCheckMixin`.
