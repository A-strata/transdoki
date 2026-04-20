# Бриф: замена `confirm()` / `alert()` на стилизованные модалки в «Мой тариф»

**Версия:** 1.0
**Дата:** 20.04.2026
**Автор:** продуктовый дизайн
**Исполнитель:** Claude Code
**Связано:** `docs/ui-guide.md` §4 (нативный `confirm()` помечен как антипаттерн), `static/billing/js/subscription.js`, `billing/templates/billing/subscription.html`.

---

## Цель

Убрать со страницы `/billing/subscription/` нативные `window.confirm()` и `window.alert()` и заменить их на стилизованные модалки, согласованные с существующим паттерном страницы (`.modal-overlay` + `data-modal-open` от `static/js/base.js` — тот же, что использует `#plan-change-modal` и `#insufficient-funds-modal`).

## Контекст и почему

`docs/ui-guide.md` §4 явно запрещает `onclick="return confirm(...)"` и нативные диалоги: «не стилизуется, выглядит чужеродно, не даёт описать последствия». На этой странице 3 `confirm()` + 2 `alert()` + 1 fallback-`alert` в `showError`. Все — legacy, написанные до закрепления паттерна модалок.

Не путать с задачей про `data-lk-modal-open` в кабинете: тот префикс был нужен из-за конфликта классов (`.lk-modal-overlay` vs `.modal-overlay`). Здесь страница уже сидит на глобальном паттерне `base.js` — берём его, не плодим второй.

## Скоуп

**В скоупе:**
- 3 `confirm()` в `subscription.js` (lines 97, 118, 141) → стилизованные confirm-модалки.
- 2 `alert()` для success-состояний (lines 102, 127) → стилизованные success-модалки. У них есть содержательные данные (`charged` сумма, `warnings[]`, `effective_at`) — теряются в нативном `alert`.
- 1 fallback `alert()` в `showError()` (line 182) → тост через паттерн `flash-wrap` (он уже используется в `showStubToast`, lines 235-255).

**Не в скоупе:**
- Бэкенд-эндпоинт preview pro-rata (показать сумму **до** клика «Перейти»). Это бэклог: требует нового view + теста + контракта JSON. Сейчас pro-rata считается только внутри `upgrade_plan()` сервиса, отдельного preview нет (`billing/views.py:253` — комментарий «pro rata вручную для UI»).
- Изменение бизнес-логики upgrade/downgrade. Только UI-обвязка.
- Стилизация `#insufficient-funds-modal` — она уже стилизована, не трогаем.

## Решение — 5 модалок + 1 тост

Все модалки строятся на существующем паттерне страницы: `<div class="modal-overlay" id="..." hidden>` + `data-modal-close` для крестика/cancel. Открываются программно: `document.getElementById(id).hidden = false`. Закрываются через `base.js` (ESC, overlay-click, `[data-modal-close]`) — без изменений в `base.js`.

### Модалка 1: `#upgrade-confirm-modal` (заменяет `confirm` в `handleUpgrade`)

**Триггер:** клик по кнопке плана с большей ценой → `handlePlanSelection` → `handleUpgrade(planCode, planName)`.

**Содержимое:**
- Заголовок: «Перейти на тариф «{planName}»?»
- Body:
  > «Сейчас спишется pro rata-разница за оставшиеся дни текущего периода. Если на балансе не хватит — мы покажем сколько нужно пополнить, тариф не сменится.»
- Действия:
  - Primary `tms-btn-primary` «Перейти» → triggers `submitUpgrade(planCode, planName)` (бывшее тело `handleUpgrade` после confirm).
  - Secondary `tms-btn-secondary` `data-modal-close` «Отмена».

**JS:** `handleUpgrade` теперь только заполняет данные и открывает модалку:
```js
function handleUpgrade(planCode, planName) {
  var modal = document.getElementById("upgrade-confirm-modal");
  modal.querySelector("[data-plan-name]").textContent = planName;
  modal.querySelector("[data-confirm-action]").dataset.planCode = planCode;
  modal.querySelector("[data-confirm-action]").dataset.planName = planName;
  modal.hidden = false;
}
```

Слушатель на `[data-confirm-action]` внутри модалки делает POST. После ответа — закрываем эту модалку, открываем `#upgrade-success-modal` (или `#insufficient-funds-modal`).

### Модалка 2: `#upgrade-success-modal` (заменяет `alert("Тариф изменён...")`)

**Триггер:** `result.body.ok === true` после upgrade-POST.

**Содержимое:**
- Иконка-галочка (как в `lk-success-ico` из кабинета — переиспользуем CSS-класс или копируем).
- Заголовок: «Тариф изменён»
- Body:
  > «Вы перешли на «{planName}». Списано: **{charged} ₽** (pro rata за оставшиеся дни периода).»
- Primary «Готово» → `data-modal-close` + `window.location.reload()` через JS-handler (или просто перезагрузка по клику кнопки).

### Модалка 3: `#downgrade-schedule-confirm-modal` (заменяет `confirm` в `handleScheduleDowngrade`)

**Триггер:** клик по плану с меньшей ценой.

**Содержимое:**
- Заголовок: «Запланировать переход на «{planName}»?»
- Body:
  > «Текущий тариф продолжит действовать до **{currentPeriodEnd}**, после чего автоматически переключится на «{planName}». До конца периода ничего не списывается.»
  > «При новом тарифе будут действовать его лимиты — если у вас уже создано больше сущностей, чем разрешает «{planName}», часть функций будет недоступна до увеличения лимита.»
- Действия:
  - Primary «Запланировать переход».
  - Secondary `data-modal-close` «Отмена».

**Источник `currentPeriodEnd`:** в `subscription.html` уже доступен `subscription.current_period_end` (используется в `lk-plan-current` шапке). Пробросить как `data-current-period-end="{{ subscription.current_period_end|date:'j E Y' }}"` в корневой `<section class="subscription-page">`. JS читает из `page.dataset.currentPeriodEnd`.

### Модалка 4: `#downgrade-schedule-success-modal` (заменяет `alert("Переход запланирован...")`)

**Триггер:** успешный POST на schedule-downgrade.

**Содержимое:**
- Иконка-галочка.
- Заголовок: «Переход запланирован»
- Body:
  > «С **{effective_at|date:'j E Y'}** ваш тариф автоматически сменится на «{planName}».»
- Если есть `result.body.warnings.length > 0`:
  > Блок warning (`alert alert-warning` или `lk-warning`) со списком:
  > «Перед переходом обратите внимание:»
  > `<ul>` из `warnings[]`.
- Primary «Понятно» → reload.

### Модалка 5: `#cancel-downgrade-confirm-modal` (заменяет `confirm` в cancel-downgrade)

**Триггер:** клик по `[data-cancel-downgrade]`.

**Содержимое:**
- Заголовок: «Отменить запланированный переход?»
- Body: «Текущий тариф останется активным после конца периода. Запланированная смена будет отменена.»
- Действия:
  - Primary `tms-btn-primary` «Отменить переход».
  - Secondary `data-modal-close` «Не отменять».

**Не делаем success-модалку для cancel** — `window.location.reload()` достаточно (страница перерисуется без блока «запланирован переход», изменение очевидно).

### Тост-fallback в `showError`

```js
function showError(msg) {
    var errBox = document.getElementById("plan-change-errors");
    if (errBox) {
        errBox.textContent = msg;
        errBox.hidden = false;
    } else {
        showStubToast(msg);  // вместо alert(msg)
    }
}
```

Функция `showStubToast` уже есть в файле (lines 235-255), переименовать в `showToast` (или оставить как есть и просто переиспользовать). Легко.

## Файлы

| Файл | Что меняем |
|---|---|
| `billing/templates/billing/subscription.html` | Добавить 5 новых `<div class="modal-overlay">` в конец `{% block content %}` (после `#plan-change-modal` и `#insufficient-funds-modal`). Пробросить `data-current-period-end` в `.subscription-page`. |
| `static/billing/js/subscription.js` | Удалить 3 `confirm()` + 2 `alert()` (lines 97, 102, 118, 127, 141). Перевести `handleUpgrade` / `handleScheduleDowngrade` / cancel-handler на схему «открыть модалку → POST из её primary-кнопки → открыть success-модалку». Заменить fallback `alert(msg)` в `showError` на тост. |
| `static/billing/css/subscription.css` | Доп. правил, скорее всего, не нужно — `.modal-overlay` / `.modal-dialog` стилизованы глобально. Если success-иконка отсутствует в CSS — добавить `.lk-success-ico` (взять из `cabinet-mockup.html`). |
| `billing/tests/test_subscription_view.py` | Не требуется новых тестов — бэкенд-логика не трогается. Если хочется — добавить мини-тест на то, что страница рендерит `#upgrade-confirm-modal` (smoke). |
| Playwright `scripts/subscription_smoke.mjs` (если уже есть) | Сценарий: выбрать более дорогой план → видим модалку → отмена; выбрать снова → подтверждение → видим success-модалку. |

## Acceptance criteria

1. На `/billing/subscription/` нет ни одного `window.confirm` / `window.alert` в DOM-event-handler'ах. Проверка: `grep -E "confirm\(|alert\(" static/billing/js/subscription.js` — пусто.
2. Клик «Сменить тариф» → выбор плана с большей ценой → открывается `#upgrade-confirm-modal` с именем плана и текстом про pro rata. ESC и клик по overlay закрывают её без действия.
3. В `#upgrade-confirm-modal` клик «Перейти» → POST → при `ok` открывается `#upgrade-success-modal` с конкретной суммой `charged ₽`. Клик «Готово» → reload.
4. В `#upgrade-confirm-modal` клик «Перейти» → POST → при HTTP 402 открывается `#insufficient-funds-modal` (как раньше), confirm-модалка автоматически закрывается перед открытием.
5. Выбор плана с меньшей ценой → открывается `#downgrade-schedule-confirm-modal` с датой `current_period_end` и предупреждением про лимиты.
6. После успешного schedule-downgrade открывается `#downgrade-schedule-success-modal` с датой `effective_at`. Если есть `warnings` — они отрендерены списком в warning-блоке внутри модалки (а не одним сплошным текстом, как в нативном alert).
7. Клик «Отменить запланированный переход» → открывается `#cancel-downgrade-confirm-modal`. Подтверждение → POST → reload без success-модалки.
8. Если в DOM нет `#plan-change-errors` (теоретический edge), `showError` показывает тост через `showStubToast` / `showToast`, а не нативный `alert`.
9. Все модалки закрываются ESC, кликом по overlay, кнопкой `data-modal-close`. Submit-кнопки сбрасывают `disabled` после закрытия (на случай если внутри `submitUpgrade` поставили `disabled` во время fetch).
10. `ruff check .` зелёный. `python manage.py test billing` зелёный. Нет регрессий по существующим тестам `test_subscription_view.py`.
11. Никаких новых миграций, новых зависимостей, изменений в `billing/services/` или `billing/views.py`.

## Open questions (если возникнут)

Если по ходу выяснится:
- В `base.js`-обвязке `data-modal-open` нет программного API «открыть модалку из JS без атрибута на кнопке» — пишем `modal.hidden = false` напрямую, как уже делает `showInsufficientFunds` (line 173). Не изобретать обёртку.
- Класс `.lk-success-ico` из кабинетного мокапа не подключён к `subscription.css` — скопировать стиль (3-4 строки) сразу в `subscription.css`, не делать общий компонент в этой задаче.
- `result.body.warnings` приходит не массивом, а строкой — это бэкенд-баг, остановиться и доложить, не парсить вручную.

## Definition of done

- 0 нативных диалогов на странице `/billing/subscription/`.
- Все 5 сценариев проходят вручную: upgrade-success, upgrade-insufficient-funds, downgrade-schedule-success-без-warnings, downgrade-schedule-success-с-warnings, cancel-downgrade.
- Существующие `billing` тесты зелёные.
- Visual review: модалки выглядят согласованно с `#plan-change-modal` (тот же `.modal-overlay`/`.modal-dialog`, кнопки `.tms-btn-primary` / `.tms-btn-secondary`).
- Бэклог-задача «pro-rata preview перед апгрейдом» вынесена в открытом виде (отдельный issue/note), но в этом PR не делается.
