# Интеграция CloudPayments — пополнение баланса

> Статус: **в разработке** (инфраструктура готова, регистрация в CloudPayments не пройдена)

---

## Обзор

Пользователь пополняет баланс своего аккаунта через платёжный виджет CloudPayments.
Деньги зачисляются автоматически при получении webhook-уведомления от CP.

**Важно**: наш сервер никогда не получает данные карты. Карта вводится
в виджете CloudPayments — данные уходят напрямую на их серверы.

---

## Схема потока платежа

```
Пользователь         Наш сервер              CloudPayments
     │                    │                        │
     │  GET /billing/deposit/                      │
     │───────────────────>│                        │
     │  Форма с суммой    │                        │
     │<───────────────────│                        │
     │                    │                        │
     │  POST /billing/deposit/ (amount=500)         │
     │───────────────────>│                        │
     │                    │ создаёт PaymentOrder   │
     │                    │ (status=pending)        │
     │  {ok:true,         │                        │
     │   widget_params}   │                        │
     │<───────────────────│                        │
     │                    │                        │
     │  JS открывает виджет CP                      │
     │──────────────────────────────────────────>  │
     │  пользователь вводит карту                  │
     │                    │                        │
     │                    │  POST /billing/cloudpayments/check/
     │                    │<───────────────────────│
     │                    │ проверяет: заказ        │
     │                    │ существует, сумма ок    │
     │                    │  {"code": 0}           │
     │                    │───────────────────────>│
     │                    │                        │ списывает с карты
     │                    │  POST /billing/cloudpayments/pay/
     │                    │<───────────────────────│
     │                    │ создаёт BillingTransaction
     │                    │ зачисляет на баланс    │
     │                    │ order.status = paid    │
     │                    │  {"code": 0}           │
     │                    │───────────────────────>│
     │  onSuccess → redirect /billing/             │
     │<───────────────────────────────────────────  │
```

Если оплата не прошла — CP присылает `POST /billing/cloudpayments/fail/`
вместо `/pay/`. Деньги с карты не списаны, `order.status` → `failed`.

---

## Файловая структура

```
billing/
  models.py          PaymentOrder, BillingTransaction
  cloudpayments.py   Сервисный слой интеграции
  forms.py           DepositForm (валидация суммы)
  views.py           DepositView + три webhook-view
  urls.py            URL-маршруты
  templates/billing/
    deposit.html     Страница пополнения
    transaction_list.html  История + кнопка "Пополнить"
```

---

## Модель `PaymentOrder`

| Поле | Тип | Описание |
|------|-----|----------|
| `order_id` | UUID | Наш ID заказа. Передаётся в CP как `InvoiceId`. CP возвращает его в каждом webhook'е |
| `account` | FK → Account | К какому аккаунту относится пополнение |
| `amount` | Decimal | Сумма в рублях |
| `status` | choices | `pending` → `paid` или `pending` → `failed` |
| `cp_transaction_id` | BigInt | ID транзакции в системе CloudPayments (для возвратов и сверки) |
| `cp_data` | JSON | Все поля из webhook payload (маска карты, IP, код авторизации и т.п.) |
| `transaction` | OneToOne → BillingTransaction | Ссылка на запись зачисления баланса. `NULL` до оплаты |
| `created_at` | DateTime | Когда создан заказ |
| `completed_at` | DateTime | Когда завершён (оплачен или отклонён) |

**Финальные статусы**: `paid` и `failed` — изменить назад нельзя (защита от гонок).

---

## Сервисный слой `billing/cloudpayments.py`

### `create_payment_order(account, amount) → dict`

Создаёт `PaymentOrder` (status=pending) и возвращает параметры для JS-виджета:

```python
{
    "publicId":    "pk_...",       # из CLOUDPAYMENTS_PUBLIC_ID в .env
    "description": "Пополнение баланса Transdoki",
    "amount":      500.0,          # float, как требует виджет
    "currency":    "RUB",
    "invoiceId":   "uuid-...",     # order.order_id
    "accountId":   "42",           # account.pk (для отчётов CP)
}
```

Выбрасывает `ValueError` если сумма вне диапазона 50–100 000 ₽.

---

### `verify_webhook_hmac(raw_body: bytes, signature: str) → bool`

Проверяет подпись запроса от CP:
- Алгоритм: `base64(HMAC-SHA256(тело_запроса, CLOUDPAYMENTS_API_SECRET))`
- Заголовок: `X-Content-HMAC`
- Использует `hmac.compare_digest` против timing attack
- Если `CLOUDPAYMENTS_API_SECRET` не задан — всегда `False`

---

### `handle_check_webhook(payload: dict) → None`

Вызывается до списания денег. Проверяет:
1. Заказ с `InvoiceId` существует
2. Сумма в payload совпадает с `order.amount`

Бросает `PaymentOrderNotFound` или `CloudPaymentsError` при проблеме.

---

### `handle_pay_webhook(payload: dict) → None`

Вызывается после успешного списания. Атомарно:
1. Блокирует `PaymentOrder` через `select_for_update`
2. Вызывает `billing.services.deposit()` → зачисляет на баланс
3. Переводит `order.status` в `paid`, заполняет `cp_transaction_id`, `cp_data`

**Идемпотентен**: повторный вызов для уже `paid` заказа — тихий `return`.

---

### `handle_fail_webhook(payload: dict) → None`

Переводит `order.status` в `failed`, сохраняет `ReasonCode`. Финансов не касается.

---

## Webhook endpoints

| URL | Метод | Назначение |
|-----|-------|-----------|
| `/billing/cloudpayments/check/` | POST | Проверка заказа до списания |
| `/billing/cloudpayments/pay/` | POST | Уведомление об успешной оплате |
| `/billing/cloudpayments/fail/` | POST | Уведомление об ошибке оплаты |

Все три endpoint'а:
- Не требуют авторизации пользователя (вызываются серверами CP)
- Проверяют HMAC-подпись в заголовке `X-Content-HMAC`
- Принимают `application/x-www-form-urlencoded` (дефолт CP) и `application/json`
- Отвечают `{"code": 0}` при успехе

**Коды ответа:**
- `{"code": 0}` — ОК
- `{"code": 10}` — постоянная ошибка (повтор не поможет)
- `{"code": 20}` — временная ошибка (CP повторит до 100 раз)

---

## Страница пользователя

**URL:** `GET /billing/deposit/`
**Доступ:** только авторизованным пользователям

Форма с полем суммы и кнопками быстрого выбора (200 / 500 / 1000 / 3000 / 5000 ₽).

**Флоу JS:**
1. `POST /billing/deposit/` (AJAX) → сервер создаёт `PaymentOrder`
2. JS получает `widget_params`, открывает виджет: `new cp.CloudPayments().pay('charge', ...)`
3. `onSuccess` → `window.location.href = '/billing/?deposited=1'`
4. `onFail` → показывает сообщение об ошибке, кнопка разблокируется

**Важно**: redirect после `onSuccess` не означает, что баланс уже обновился.
Webhook может прийти чуть позже. Страница `/billing/` покажет актуальный баланс.

---

## Конфигурация (.env)

```env
# Публичный ID магазина (из личного кабинета CloudPayments → настройки сайта)
CLOUDPAYMENTS_PUBLIC_ID=pk_...

# API-пароль (из личного кабинета CloudPayments → настройки сайта)
# Используется для верификации HMAC webhook'ов
CLOUDPAYMENTS_API_SECRET=...
```

Пока переменные не заданы:
- Виджет откроется, но платёж не пройдёт (`publicId` пустой)
- Все webhook'и будут отклоняться с HTTP 403 (HMAC не пройдёт)

---

## Что нужно сделать после регистрации в CloudPayments

- [ ] Добавить `CLOUDPAYMENTS_PUBLIC_ID` и `CLOUDPAYMENTS_API_SECRET` в `.env` (и на проде)
- [ ] В личном кабинете CP → **Настройки** → **Уведомления** прописать три URL:
  - Check: `https://transdoki.ru/billing/cloudpayments/check/`
  - Pay: `https://transdoki.ru/billing/cloudpayments/pay/`
  - Fail: `https://transdoki.ru/billing/cloudpayments/fail/`
- [ ] Провести тестовый платёж в тестовом режиме CP (тестовые карты — в документации CP)
- [ ] Убедиться что `PaymentOrder.status` переходит в `paid` и баланс зачисляется

---

## Тестирование (чеклист)

### До регистрации (можно проверить уже сейчас)

- [ ] `GET /billing/deposit/` открывается, форма отображается
- [ ] Кнопки быстрого выбора суммы заполняют поле
- [ ] Валидация: сумма < 50 ₽ → ошибка "Минимальная сумма — 50 ₽"
- [ ] Валидация: сумма > 100 000 ₽ → ошибка
- [ ] Пустое поле → ошибка
- [ ] Кнопка "Пополнить" в `/billing/` ведёт на форму

### После регистрации (тестовый режим CP)

- [ ] Форма → виджет открывается с правильной суммой и описанием
- [ ] Оплата тестовой картой `4111 1111 1111 1111` → `PaymentOrder.status = paid`
- [ ] Баланс аккаунта увеличился на нужную сумму
- [ ] В `/billing/` появилась транзакция типа "Пополнение"
- [ ] Повторный webhook (симуляция дубля) — повторного зачисления нет
- [ ] Оплата картой с ошибкой → `PaymentOrder.status = failed`, баланс не изменился
- [ ] HMAC с неверным секретом → webhook возвращает HTTP 403

### Безопасность

- [ ] Webhook без заголовка `X-Content-HMAC` → HTTP 403
- [ ] Webhook с неверной подписью → HTTP 403
- [ ] Check с суммой, отличной от `order.amount` → `{"code": 10}`
- [ ] Check с несуществующим `InvoiceId` → `{"code": 10}`
- [ ] Pay для уже оплаченного заказа → `{"code": 0}`, повторного зачисления нет

---

## Возможные проблемы и решения

| Проблема | Вероятная причина | Решение |
|----------|------------------|---------|
| Webhook возвращает HTTP 403 | `CLOUDPAYMENTS_API_SECRET` не задан или неверный | Проверить `.env`, перезапустить сервер |
| Баланс не зачисляется после оплаты | Check вернул `{"code": 10}` или Pay webhook не дошёл | Посмотреть `PaymentOrder` в Django Admin, проверить логи |
| Виджет не открывается | `publicId` пустой или скрипт CP не загрузился | Проверить консоль браузера и `.env` |
| `PaymentOrder` в статусе `pending` долго | Pay webhook не пришёл | CP повторит автоматически; проверить доступность URL с внешнего IP |

---

*Последнее обновление: 2026-03-24*
