# transdoki — UI/UX Guide

> Живой документ. Обновлять при добавлении новых компонентов или изменении паттернов.

---

## 1. Принципы

- **Минимализм без потери функциональности** — каждый элемент должен быть оправдан
- **Предсказуемость** — одинаковые сущности выглядят одинаково везде
- **Не прерывать пользователя** — после действий (сохранение, фиксация) держать его в контексте, а не кидать наверх страницы
- **Иерархия через типографику и отступы**, не через цвет
- **Явные состояния** — каждый интерактивный элемент и каждый процесс (загрузка, ошибка, пустота) должен иметь визуальное представление

---

## 2. Токены (CSS-переменные)

Все значения берутся из `:root` в `base.html`. Не использовать хардкод там, где есть переменная.

```css
/* Цвета */
--bg: #f6f7fb          /* фон страницы */
--surface: #ffffff     /* поверхность карточек */
--text: #111827        /* основной текст */
--muted: #6b7280       /* второстепенный текст */
--border: #e5e7eb              /* структурные разделители, каркас карточек */
--border-interactive: #b0b7c3  /* интерактивные контейнеры: кнопки, карточки маршрута, дропдауны */
--border-input:       #a0a8b4  /* поля ввода в покое */
--border-input-hover: #8b94a6  /* поля ввода при hover */
--hover: #f8fafc       /* hover строк таблицы + фон раскрытой карточки (route builder и др.) */
--hover-active: #eef6ff /* подсветка строк с активным элементом (открытое меню) */

/* Акцент */
--primary: #2563eb
--primary-hover: #1d4ed8

/* Деструктивные действия */
--danger: #dc2626
--danger-hover: #b91c1c

/* Наложения и специальные поверхности */
--modal-overlay:       rgba(0, 0, 0, 0.4)    /* затемнение за модальным окном */
--surface-translucent: rgba(255, 255, 255, 0.92) /* полупрозрачный фон навбара (frosted glass) */
--hover-inverse:       rgba(0, 0, 0, 0.05)   /* тёмный hover поверх цветного фона (flash-кнопки) */
--primary-ring:        rgba(37, 99, 235, 0.3) /* outline фокуса и hover-рамки в цвет акцента */

/* Геометрия */
--radius: 12px         /* основной radius */
--radius-sm: 10px
--shadow: 0 8px 24px rgba(15, 23, 42, 0.06)
--container: 1200px

/* Типографика (шкала ×1.25 — major third) */
--text-xs:   0.75rem    /* 12px — бейджи, хедеры таблиц */
--text-sm:   0.875rem   /* 14px — метки форм, подписи, вспомогательный текст */
--text-base: 1rem       /* 16px — тело, значения, заголовки секций (через weight) */
--text-lg:   1.25rem    /* 20px — заголовки карточек / компонентов */
--text-xl:   1.5rem     /* 24px — заголовок страницы */

/* Z-index слои */
--z-sticky-cell:     20
--z-sticky-header:   30
--z-sticky-actions:  40
--z-navbar:          50
--z-toast:           70
--z-inline-dropdown: 200
--z-modal:           1000
--z-autocomplete:    1100
--z-filter-dropdown: 1200
--z-column-panel:    1300
--z-actions-menu:    1400

/* Семантические состояния */
--success-text:   #16a34a
--success-bg:     #f0fdf4
--success-border: #bbf7d0

--warning-text:   #d97706
--warning-bg:     #fffbeb
--warning-border: #fde68a

--error-text:     #dc2626
--error-bg:       #fef2f2
--error-border:   #fecaca

--info-text:      #0e7490
--info-bg:        #ecfeff
--info-border:    #a5f3fc

--neutral-text:   #6b7280
--neutral-bg:     #f3f4f6
--neutral-border: #e5e7eb
```

### Семантическая палитра состояний

| Состояние | Текст              | Фон              | Рамка              |
|-----------|--------------------|--------------------|---------------------|
| success   | `--success-text`   | `--success-bg`     | `--success-border`  |
| warning   | `--warning-text`   | `--warning-bg`     | `--warning-border`  |
| error     | `--error-text`     | `--error-bg`       | `--error-border`    |
| info      | `--info-text`      | `--info-bg`        | `--info-border`     |
| neutral   | `--neutral-text`   | `--neutral-bg`     | `--neutral-border`  |

---

## 3. Типографика

Шрифт: **Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif**

### Шкала размеров (×1.25 — major third)

В проекте используются **5 ступеней**. Шаг между ними — множитель ×1.25, каждая ступень визуально отличима от соседней. При создании новых шаблонов использовать только CSS-переменные, не произвольные значения.

| Переменная    | Размер     | ~px | Роль                                          | Weight  |
|---------------|------------|-----|-----------------------------------------------|---------|
| `--text-xs`   | `0.75rem`  | 12  | Бейджи, хедеры таблиц                        | 600     |
| `--text-sm`   | `0.875rem` | 14  | Метки форм, kv-label, подписи, вспомогательный текст | 400–600 |
| `--text-base` | `1rem`     | 16  | Тело текста, значения, **заголовки секций** (через `font-weight: 700`) | 400–700 |
| `--text-lg`   | `1.25rem`  | 20  | Заголовки карточек / компонентов              | 700     |
| `--text-xl`   | `1.5rem`   | 24  | Заголовок страницы                            | 700     |

Заголовок секции и обычный текст — один размер (`--text-base`), различаются жирностью. Это сокращает количество ступеней без потери иерархии.

Для заголовка страницы на полноширинных макетах (списки, детальные страницы) допускается `clamp(1.25rem, 1.8vw, 1.5rem)` вместо фиксированного `1.5rem`. Это единственное исключение. Для компонентов с фиксированной шириной (карточки, модалки, формы) — только фиксированный `rem`.

> ⚠️ **Техдолг**: в проекте сейчас 16+ разных font-size — от 0.7rem до 1.05rem с шагом 0.01–0.02rem. При рефакторинге приводить к переменным из таблицы выше. Новый код — **только через переменные**.

---

## 4. Кнопки

Базовый класс: `.tms-btn`. Всегда сочетается с модификатором.

```html
<button class="tms-btn tms-btn-primary">Сохранить</button>
<button class="tms-btn tms-btn-secondary">Отмена</button>
<a href="..." class="tms-btn tms-btn-secondary">Редактировать</a>
```

| Класс                | Когда использовать                                         |
|----------------------|------------------------------------------------------------|
| `tms-btn-primary`    | Главное действие страницы (одно на страницу)               |
| `tms-btn-secondary`  | Вторичные действия: редактировать, скачать, к списку       |
| `tms-btn-light`      | Лёгкая навигация: «Назад», «К списку» без акцента          |
| `tms-btn-danger`     | Деструктивные действия: удалить, отменить необратимо (красный, `--danger`) |
| `tms-btn-fix`        | Фиксация/подтверждение финансовых данных (зелёный)         |
| `tms-btn-add`        | Добавить строку, добавить элемент (иконка +)               |
| `tms-btn-sm`         | Размерный модификатор для кнопок внутри таблиц и компактных блоков |

**Правила**:
- Не более одной `tms-btn-primary` в видимой области. Остальные — secondary или light
- `tms-btn-danger` — **только** внутри подтверждающих контекстов (confirm-inline, модалка). Не ставить как основную кнопку в toolbar или форме

**Недоступные кнопки**: использовать нативный атрибут `disabled`, а не CSS-класс. Класс вместо атрибута — антипаттерн: теряется доступность (keyboard nav, screen readers), форма не блокируется. Курсор задаётся через CSS:

```css
button:disabled {
    opacity: 0.55;
    cursor: not-allowed;
    pointer-events: none;
}
```

### Состояния интерактивных элементов

Каждый кликабельный элемент (кнопка, ссылка, строка таблицы) должен иметь визуальный отклик на все состояния:

| Состояние | Визуал | CSS |
|-----------|--------|-----|
| default   | базовый стиль | — |
| hover     | затемнение фона на 8–10% | `transition: 0.15s ease` |
| focus     | синий outline | `outline: 3px solid rgba(37, 99, 235, 0.3)` |
| active    | лёгкое нажатие | `transform: scale(0.98)` или darken 15% |
| disabled  | полупрозрачный, некликабельный | `opacity: 0.55; pointer-events: none` |
| loading   | текст меняется, кнопка disabled | `data-loading-text` паттерн |

**Правило анимаций**: все hover/focus-переходы — `transition: 0.15s ease`. Без анимаций при загрузке страницы. Без `animation` кроме toast-уведомлений.

### Подтверждение деструктивных действий

`onclick="return confirm(...)"` — **антипаттерн**. Нативный `confirm()` не стилизуется, выглядит чужеродно и не даёт описать последствия.

**Целевой паттерн** — inline-подтверждение: при нажатии кнопки «Удалить» она заменяется на блок с вопросом и двумя кнопками:

```html
<div class="confirm-inline" data-confirm>
    <button type="button" class="tms-btn tms-btn-danger tms-btn-sm"
            data-confirm-trigger>Удалить</button>
    <div class="confirm-inline-prompt" hidden>
        <span>Удалить?</span>
        <button type="submit" class="tms-btn tms-btn-danger tms-btn-sm">Да</button>
        <button type="button" class="tms-btn tms-btn-secondary tms-btn-sm"
                data-confirm-cancel>Нет</button>
    </div>
</div>
```

Для критичных действий (удаление организации, пользователя) — модальное окно с описанием последствий.

### Модальные окна

Все модалки строятся из глобальных компонентов (`static/css/globals.css` + `static/js/base.js`). Не создавать отдельные CSS-файлы для стилей модалок.

**Структура (подтверждение):**

```html
<div class="modal-overlay" id="my-modal" hidden>
    <div class="modal-dialog">
        <h3 class="modal-title">Заголовок</h3>
        <p class="modal-body">Описание последствий</p>
        <div class="modal-actions">
            <button class="tms-btn tms-btn-danger">Удалить</button>
            <button class="tms-btn tms-btn-secondary" data-modal-close>Отмена</button>
        </div>
    </div>
</div>
```

**Структура (форма):**

```html
<div class="modal-overlay" id="my-modal" hidden>
    <div class="modal-dialog modal-dialog--wide">
        <h3 class="modal-title">Заголовок</h3>
        <p class="modal-body">Контекст</p>
        <form id="my-form" novalidate>
            {% csrf_token %}
            <div class="modal-fields">
                <div class="modal-field modal-field--full">
                    <label>На всю ширину</label>
                    <select>...</select>
                </div>
                <div class="modal-field">
                    <label>Поле 1</label>
                    <input type="text">
                </div>
                <div class="modal-field">
                    <label>Поле 2</label>
                    <input type="text">
                </div>
            </div>
            <div class="modal-form-errors" id="form-errors" hidden></div>
            <div class="modal-actions">
                <button type="submit" class="tms-btn tms-btn-primary">Сохранить</button>
                <button type="button" class="tms-btn tms-btn-secondary" data-modal-close>Отмена</button>
            </div>
        </form>
    </div>
</div>
```

**Открытие/закрытие** — через `data-`атрибуты (JS в `base.js`):

```html
<button data-modal-open="my-modal">Открыть</button>    <!-- открывает -->
<button data-modal-close>Отмена</button>                <!-- закрывает -->
<!-- Также: клик по overlay, Escape -->
```

| Класс | Назначение |
|---|---|
| `.modal-overlay` | Затемнённый фон, `position: fixed`, `z-index: var(--z-modal)` |
| `.modal-dialog` | Белая карточка, `max-width: 420px` |
| `.modal-dialog--wide` | Расширенная карточка, `max-width: 520px` |
| `.modal-title` | Заголовок модалки |
| `.modal-body` | Описательный текст |
| `.modal-fields` | CSS Grid `1fr 1fr` для полей формы |
| `.modal-field` | Обёртка поля (label + input/select) |
| `.modal-field--full` | Поле на всю ширину (`grid-column: 1 / -1`) |
| `.modal-field-error` | Текст ошибки под полем |
| `.modal-form-errors` | Блок общих ошибок формы |
| `.modal-actions` | Ряд кнопок внизу |

**Правила:**
- Ошибки валидации — inline под полями (`.is-invalid` + `.modal-field-error`), не `alert()`
- При закрытии — сбрасывать форму и ошибки
- AJAX-формы: отправка через `fetch`, при успехе `location.reload()` или обновление DOM

---

## 5. Уведомления (Flash-сообщения)

### ✅ Правильно

В `views.py` через Django messages framework:

```python
messages.success(request, "Данные сохранены")
messages.error(request, "Произошла ошибка")
messages.warning(request, "Обратите внимание")
```

`base.html` автоматически рендерит их как фиксированный toast вверху экрана (позиция `fixed`, z-index `var(--z-toast)`). Success и info скрываются через 4 секунды, error/warning — по клику.

### ❌ Запрещено

Не дублировать блок `{% if messages %}` в шаблонах страниц — `base.html` уже делает это. Такой код приводит к тому, что сообщение либо не показывается (уже было потреблено), либо выводится как статичная карточка без анимации и автоскрытия.

### Inline-алерты (не toast)

Для постоянных статусных блоков внутри страницы используется `.alert`:

```html
<div class="alert alert-warning">Путевой лист закрыт, редактирование недоступно.</div>
```

Классы: `alert-success`, `alert-error`, `alert-warning`, `alert-info`.

---

## 6. Сохранение позиции прокрутки

После POST-запроса, изменяющего данные на странице, пользователь должен остаться в том же контексте — не улетать наверх.

**Паттерн**: якорная навигация.

1. Добавить `id` к целевой секции в шаблоне:
```html
<div class="section" id="finances">
```

2. Добавить `scroll-margin-top` в CSS шаблона (учитывает высоту sticky navbar):
```css
#finances {
    scroll-margin-top: 90px;
}
```

3. В `views.py` редиректить с якорем:
```python
from django.urls import reverse

url = reverse("app:detail", args=[pk]) + "#finances"
return redirect(url)
```

**Правило**: любой POST, который не меняет страницу полностью (создание, переход на другой объект), должен возвращать пользователя к месту действия.

**Реализовано**: кабинет пользователей (`#user-{id}`), фиксация финансов рейса (`#finances`).

### Изменение коллекции на детальной странице (fetch + DOM update)

Когда пользователь добавляет или удаляет элемент коллекции на детальной странице (вложение, контакт и т.п.) — предпочтительнее **обновить DOM** без перезагрузки страницы.

**Почему**: полная перезагрузка после лёгкой операции (добавить/удалить один элемент) ощущается как откат — страница моргает и прокрутка сбрасывается.

**Паттерн:**

1. **View** — возвращает `JsonResponse` для AJAX, обычный redirect для non-JS:
```python
def post(self, request, pk, item_pk):
    item = get_object_or_404(...)
    item.delete()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    messages.success(request, "Удалено.")
    return redirect("app:detail", pk=pk)
```

2. **JS** — перехват submit, fetch POST, обновление DOM:
```javascript
// Удаление: убрать элемент из DOM
triggerButton.closest('.list-item').remove();
// Показать пустое состояние если элементов не осталось

// Добавление: вставить новый элемент в список
list.appendChild(buildItem(responseData));
// Убрать пустое состояние если было
```

3. **Кнопка-триггер** (удаление) хранит ссылку на элемент через `data-modal-open` + `data-delete-url`.

4. **Состояния загрузки**: кнопка submit получает `disabled` + изменённый текст на время запроса.

**Реализовано**: вложения рейса — загрузка и удаление (`trip_detail`).

---

## 7. Статические файлы (CSS и JS)

Стили и скрипты — только во внешних файлах, подключаемых через `{% static %}`. Инлайн `<style>` и `<script>` в шаблонах запрещены. Это Django-way: файлы кешируются браузером и корректно подхватываются `collectstatic`.

### Структура

```
static/
  css/forms.css        # общие компоненты форм (.field, .errorlist, .helptext, .form-errors)
  css/nav.css          # навбар
  css/tables.css       # таблицы
  css/globals.css      # глобальные компоненты (модалки, алерты, бейджи)
  js/base.js           # глобальный JS (модалки, data-confirm, data-loading)
  js/password_toggle.js
  js/phone_mask.js
  js/code_mask.js
  <app>/css/           # стили конкретного приложения
  <app>/js/            # скрипты конкретного приложения
```

### Правила

- Повторяющиеся стили/скрипты (2+ шаблона) → `static/css/` или `static/js/`, подключить в `base.html`
- Специфичные для одного шаблона → `static/<app>/css/<template>.css` или `static/<app>/js/<script>.js`, подключить через `{% block head %}` / `{% block extra_js %}`
- Инлайн `<style>` и `<script>` — **запрещены**, даже если код кажется мелким

### Глобальный CSS reset (base.html)

`<button>`, `<input>`, `<select>`, `<textarea>` не наследуют `font-family` по умолчанию — браузер подставляет системный шрифт. Глобальный сброс в `base.html` устраняет это для всего проекта:

```css
button, input, select, textarea {
    font-family: inherit;
}
```

Это уже прописано в `base.html`. **Не добавлять `font-family: inherit` в компонентные CSS-файлы** — это решается один раз глобально.

### Передача Django-данных в JS

Если скрипту нужны URL или контекстные данные — передавать через `data-`атрибуты в HTML, читать из внешнего JS:

```html
<!-- в шаблоне -->
<div class="inn-wrap"
     data-api-url="{% url 'organizations:api_suggestions_by_inn' %}"
     data-suggest-url="{% url 'organizations:api_party_suggest' %}">
</div>
```

```javascript
// в static/<app>/js/script.js
const wrap = document.querySelector('.inn-wrap');
const apiUrl = wrap.dataset.apiUrl;
const suggestUrl = wrap.dataset.suggestUrl;
```

Инлайн-скрипт с `{% url %}` или переменными контекста — **не исключение**, а повод добавить `data-`атрибут.

### `password_toggle.js` — важно

Скрипт **сам** оборачивает каждый `<input type="password">` в `.pwd-wrap` и добавляет кнопку-глазок. Не оборачивать поля пароля в `.pwd-wrap` вручную в шаблоне — будет двойная обёртка.

---

## 8. Z-index слои

Использовать только CSS-переменные из `:root` (раздел 2). Не использовать произвольные числа.

| Переменная            | Значение | Назначение                                   |
|-----------------------|----------|----------------------------------------------|
| (нет, базовый)        | 0        | базовый контент                              |
| `--z-sticky-cell`     | 20       | sticky ячейки таблицы (td actions)           |
| `--z-sticky-header`   | 30       | sticky заголовки таблицы                     |
| `--z-sticky-actions`  | 40       | sticky заголовок колонки actions             |
| `--z-navbar`          | 50       | navbar                                        |
| `--z-toast`           | 70       | flash-wrap (toast уведомления)               |
| `--z-inline-dropdown` | 200      | inline-дропдауны внутри форм (подсказки ИНН) |
| `--z-modal`           | 1000     | модальные overlay                            |
| `--z-autocomplete`    | 1100     | autocomplete-dropdown в полях (trips/waybills)|
| `--z-filter-dropdown` | 1200     | filter-dropdown-panel                        |
| `--z-column-panel`    | 1300     | visibility-panel (настройка колонок)         |
| `--z-actions-menu`    | 1400     | actions-menu (dropdown в таблице)            |

**Правило**: при добавлении нового слоя — сначала проверить, подходит ли существующий. Если нужен новый — добавить переменную в `:root` и в эту таблицу.

> **Рекомендация на будущее**: при рефакторинге модалок применить `isolation: isolate` на `.modal-overlay`. Это создаёт изолированный stacking context — внутри модалки можно использовать z-index 1, 2, 3 без конфликтов с остальной страницей. Тогда дропдауны и автокомплиты внутри модалок не потребуют значений выше `--z-modal`.

---

## 9. Карточки и структура страниц

### Основная карточка

```html
<div class="card">
    <!-- контент -->
</div>
```

`card` = `page-card` по семантике — **использовать единый класс `card`**.

> ⚠️ **Техдолг**: в проекте сосуществуют `.card` и `.page-card` с почти идентичными стилями. При рефакторинге унифицировать в `.card`.

### Секция внутри карточки

```html
<div class="section" id="якорь-если-нужен">
    <h2 class="section-title">Название секции</h2>
    <!-- контент секции -->
</div>
```

### Детальная страница (стандартный макет)

```html
<div class="detail-layout">
    <div class="detail-main">
        <!-- основной контент, секции -->
    </div>
    <div class="detail-sidebar">
        <!-- дополнительные действия, формы -->
    </div>
</div>
```

Сетка: `2fr 380px`, на `<= 980px` переходит в 1 колонку (sidebar уходит наверх).

---

## 10. Key-Value сетка

Для отображения атрибутов объекта (детальные страницы).

```html
<div class="kv-grid">
    <div class="kv">
        <p class="kv-label">Заказчик</p>
        <p class="kv-value">ООО «Ромашка»</p>
    </div>
    <div class="kv kv--full">
        <!-- занимает обе колонки -->
        <p class="kv-label">Комментарий</p>
        <p class="kv-value">{{ trip.comments|default:"—" }}</p>
    </div>
</div>
```

> ⚠️ **Техдолг**: параллельно существует `.info-grid` / `.info-item` (waybill_detail) с тем же назначением. При рефакторинге привести к `.kv-grid`.

---

## 11. Бейджи статусов

### Целевой компонент: `.status-badge`

Единый компонент для всех статусных бейджей. Модификаторы — по **семантическому цвету**, а не по бизнес-статусу:

```html
<span class="status-badge status-badge--success">Оплачен</span>
<span class="status-badge status-badge--warning">Ожидает</span>
<span class="status-badge status-badge--error">Отменён</span>
<span class="status-badge status-badge--info">В работе</span>
<span class="status-badge status-badge--neutral">Черновик</span>
```

Цвета берутся из семантической палитры состояний (раздел 2).

### Маппинг существующих статусов

| Сущность       | Статус              | Модификатор  |
|----------------|---------------------|--------------|
| Рейс (финансы) | Открыт              | `--neutral`  |
| Рейс (финансы) | Зафиксирован        | `--info`     |
| Рейс (финансы) | Документы выставлены | `--warning`  |
| Рейс (финансы) | Оплачен             | `--success`  |
| Путевой лист   | Открыт              | `--info`     |
| Путевой лист   | Закрыт              | `--neutral`  |

### Текущие реализации (техдолг)

> ⚠️ В проекте три системы бейджей: `.fin-badge`, `.wl-status`, `.badge` (timeline). Новый код писать через `.status-badge`. При рефакторинге — переводить старые бейджи на `.status-badge`.

### Баланс в навбаре

Автоматически проставляется через контекст-процессор. Классы: `.balance-ok`, `.balance-warn`, `.balance-danger`, `.balance-exempt`. Это **не** бейдж статуса — отдельный компонент, не трогать.

---

## 12. Формы

### Структура

```html
<div class="form-card">
    <div class="section">
        <h2 class="section-title">Основное</h2>
        <div class="fields-grid">
            <div class="field">
                {{ form.name.label_tag }}
                {{ form.name }}
                {{ form.name.errors }}
                {% if form.name.help_text %}
                    <small class="helptext">{{ form.name.help_text|safe }}</small>
                {% endif %}
            </div>
            <div class="field field--full">
                <!-- поле на всю ширину -->
            </div>
        </div>
    </div>
</div>
```

> `{{ field.errors }}` рендерится Django как `<ul class="errorlist">` автоматически — не оборачивать вручную. Стили `.errorlist` и `.helptext` определены в `static/css/forms.css`.

### Ширина полей: соответствие длине данных

Ширина поля должна подсказывать ожидаемый объём ввода (**affordance**). Растянутое на 100% поле для 10-значного ИНН создаёт ложное ожидание длинного ввода и разрывает связь между полем и контекстной кнопкой (нарушение закона Фиттса).

| Тип данных | Рекомендуемая ширина | Обоснование |
|---|---|---|
| ИНН (10–12 цифр) | `280px` | 12 символов + padding |
| КПП (9 цифр), ОГРН (13 цифр) | `220px` | числовые реквизиты |
| Телефон, email | `280–320px` | контактные данные |
| Название, адрес, комментарий | `100%` | длинный свободный текст |

**Правила:**
- Поля с предсказуемой длиной (числовые коды, телефоны) — ограничивать `width` в CSS. Не `max-width` на `1fr` grid-колонке (трек всё равно растянется), а фиксированная ширина контейнера поля.
- Кнопка, связанная с полем (напр. «Заполнить по ИНН»), ставится вплотную к полю — не через всю ширину формы.

### Чекбокс / Toggle

Для бинарных опций использовать `.toggle-switch`:

```html
<div class="form-group-checkbox">
    <label class="toggle-switch">
        <input type="checkbox" class="toggle-input" name="is_active">
        <span class="toggle-slider"></span>
    </label>
    <label>Активен</label>
</div>
```

Обычный `<input type="checkbox">` — только для множественного выбора (чекбокс-список).

### Ошибки формы (верхний блок)

```html
{% if form.non_field_errors %}
    <div class="form-errors">
        {% for error in form.non_field_errors %}
            <p>{{ error }}</p>
        {% endfor %}
    </div>
{% endif %}
```

### Зависимые поля (Cascading Selects)

Когда значение одного поля определяет содержимое другого (организация → водители, водитель → ТС).

**Паттерн:**

1. **Родительское поле** — `data-cascade-source` с указанием URL:
```html
<select name="organization"
        data-cascade-source
        data-cascade-url="{% url 'persons:api_by_org' %}"
        data-cascade-target="#id_driver">
    ...
</select>
```

2. **Зависимое поле** — обычный `<select>`, становится целью:
```html
<select name="driver" id="id_driver">
    <option value="">Выберите водителя</option>
</select>
```

3. **JS-обработчик** (`static/js/cascade_select.js`):
```javascript
document.querySelectorAll('[data-cascade-source]').forEach(source => {
    source.addEventListener('change', async () => {
        const target = document.querySelector(source.dataset.cascadeTarget);
        const url = `${source.dataset.cascadeUrl}?${source.name}=${source.value}`;

        // Состояние загрузки
        target.disabled = true;
        target.innerHTML = '<option value="">Загрузка...</option>';

        try {
            const resp = await fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const items = await resp.json();

            target.innerHTML = '<option value="">Выберите</option>';
            items.forEach(item => {
                const opt = document.createElement('option');
                opt.value = item.id;
                opt.textContent = item.name;
                target.appendChild(opt);
            });
        } catch {
            target.innerHTML = '<option value="">Ошибка загрузки</option>';
        } finally {
            target.disabled = false;
        }
    });
});
```

**Правила:**
- При очистке родителя — сбрасывать зависимое поле в дефолтное состояние
- При ошибке загрузки — показывать «Ошибка загрузки» в option, не оставлять пустым
- View для API — возвращает JSON-список `[{id, name}, ...]`, проверяет `is_authenticated`

---

## 13. Таблицы

Используется только в списковых представлениях.

### Базовая структура

```html
<div class="table-card">
    <div class="table-wrap" data-drag-scroll>
        <table class="tms-table" data-trips-table>
            <thead>
                <tr>
                    <th data-col="name">Название</th>
                    <th data-col="date">Дата</th>
                    <th class="row-actions-cell"></th>
                </tr>
            </thead>
            <tbody>
                <tr data-trip-row>
                    <td data-col="name">Значение</td>
                    <td data-col="date">01.01.2026</td>
                    <td class="row-actions-cell" data-row-actions>
                        <div class="row-actions">
                            <!-- hover-иконки -->
                        </div>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
</div>
```

**Правила**:
- `table-layout: fixed`, ширина таблицы = сумма колонок или ширина контейнера
- Spacer-колонка (`.col-spacer`) вставляется JS последней, заполняет разницу при малом количестве столбцов
- Заголовки: uppercase, `var(--text-xs)`, `--muted` цвет
- Ячейки: `var(--text-sm)`, строки с `cursor: grab` для drag-scroll
- Hover строк: `var(--hover)`

### Действия строки (hover-иконки)

Действия над записью в таблицах и компактных списках — не в отдельном столбце и не постоянно видимыми кнопками, а в иконках, появляющихся при наведении на строку. В карточках деталей, формах и модалках действия остаются обычными кнопками `.tms-btn`.

```html
<td class="row-actions-cell" data-row-actions>
    <div class="row-actions">
        <a href="..." class="row-action row-action--view" title="Просмотр">
            <!-- SVG глаз 16×16 -->
        </a>
        <a href="..." class="row-action row-action--copy" title="Дублировать">
            <!-- SVG копия 16×16 -->
        </a>
        <div class="row-action-docs" data-docs-dropdown>
            <button type="button" class="row-action row-action--print"
                    title="Документы" data-docs-toggle>
                <!-- SVG принтер 16×16 -->
            </button>
            <div class="docs-menu" data-docs-menu>
                <a href="...">Скачать документ</a>
            </div>
        </div>
    </div>
</td>
```

**Правила**:
- `.row-actions-cell` — sticky `right: 0`, ширина 100px, `overflow: visible`
- `.row-actions` — `opacity: 0` → `1` при hover строки или при открытом меню (`is-docs-open`)
- `.row-action` — 28×28px, иконка 16×16px SVG (см. раздел 18 «Иконки»)
- Цвета hover: `--view` синий, `--copy` зелёный, `--print` синий
- Docs-dropdown: меню переносится в `body` (обход `overflow: hidden`), `position: fixed`, умное позиционирование, плавное появление (0.15s)
- При открытом меню строка подсвечивается `var(--hover-active)`

### Resize колонок

- Handle на правой стороне `th[data-col]` — `.col-resize-handle`, hit area 16px, линия 2px
- Доп. handle на левой стороне `.row-actions-cell` header (`.col-resize-edge`) — управляет последним видимым столбцом, всегда доступен
- Ширины по умолчанию подбираются по контенту (заголовок + данные), max 300px
- Double-click на handle — авто-подбор ширины
- Ширины, порядок, видимость сохраняются в `localStorage`

---

## 14. Списковая страница (стандартный макет)

Все списки основных сущностей строятся по единому каркасу:

```html
<div class="ENTITY-page">
    <div class="list-toolbar">
        <div class="list-toolbar-left">
            <h1>Заголовок</h1>
            <p class="list-subtitle">Пояснение (опционально)</p>
        </div>
        <div class="list-toolbar-right">
            <a href="{% url 'app:create' %}" class="tms-btn tms-btn-primary">+ Создать</a>
            <!-- фильтры, если есть -->
        </div>
    </div>

    <div class="table-card">
        <div class="table-wrap" data-drag-scroll>
            <table class="tms-table">
                <thead>...</thead>
                <tbody>
                    <!-- данные или empty-state -->
                </tbody>
            </table>
        </div>
    </div>

    <nav class="pagination">
        <!-- если есть пагинация -->
    </nav>
</div>
```

**Правила**:
- Обёртка: `.ENTITY-page` (например `.trips-page`, `.vehicles-page`)
- Тулбар: заголовок слева, кнопка создания справа
- Кнопка «+ Создать» — обязательна в каждом списке
- Таблица: всегда `.tms-table` внутри `.table-card` > `.table-wrap`
- Действия строки: hover-иконки в `.row-actions-cell` (см. раздел 13)
- CSS — только во внешних файлах: `static/<app>/css/<entity>_list.css`

### Живой поиск, сортировка, пагинация (паттерн Partial HTML over Fetch)

Списковые страницы с поиском/сортировкой/пагинацией используют серверный partial-рендеринг вместо полной перезагрузки страницы.

**Архитектура:**

1. **Partial-шаблон** — таблица + pagination footer выносятся в `<app>/templates/<app>/<entity>_list_table.html`. Основной шаблон подключает через `{% include %}` внутри контейнера `<div data-list-content>`.

2. **View** — один view, два режима:
   - Обычный запрос → полная страница (`base.html` + контент)
   - AJAX (`X-Requested-With: XMLHttpRequest`) → только partial-фрагмент

```python
def get_template_names(self):
    if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return [self.partial_template_name]
    return [self.template_name]
```

3. **JS** — `fetch` + замена `innerHTML` контейнера `[data-list-content]`:
   - Поиск: debounce 300ms, `AbortController` для отмены предыдущего запроса
   - Сортировка, пагинация, page-size: перехват кликов внутри контейнера
   - `history.pushState` + обработка `popstate` для навигации «Назад»/«Вперёд»
   - После замены DOM — перепривязка обработчиков (`bindContentEvents`)

4. **Graceful degradation** — без JS страница работает как обычный GET с перезагрузкой.

**Реализовано**: список контрагентов (`organizations`), список своих компаний.

**Структура файлов:**

```
<app>/
  templates/<app>/
    <entity>_list.html         # основной шаблон (тулбар + include)
    <entity>_list_table.html   # partial (таблица + pagination footer)
  static/<app>/js/
    <entity>_list.js           # fetch + DOM + pushState
```

**Правила:**
- Поиск сбрасывает пагинацию на первую страницу
- Сортировка сбрасывает на первую страницу
- Смена page-size сбрасывает на первую страницу
- Счётчик «Показано X–Y из Z» входит в partial и обновляется автоматически
- URL всегда отражает текущее состояние (bookmarkable)

---

## 15. Пустые состояния

Когда нет данных — не оставлять пустое место, показывать `.empty-state`:

```html
<div class="empty-state">
    <p>Рейсов пока нет. <a href="{% url 'trips:create' %}">Создать первый</a>.</p>
</div>
```

---

## 16. Якоря и прокрутка (паттерн)

| Страница              | Якорь          | Применяется в         |
|-----------------------|----------------|-----------------------|
| `accounts:cabinet`    | `#user-{id}`   | После изменения роли  |
| `trips:detail`        | `#finances`    | После фиксации суммы  |

При добавлении новых POST-действий на длинных страницах — добавлять якорь по аналогии.

---

## 17. Адаптивность

Проект ориентирован на desktop (B2B, работа за ПК). Минимальная поддерживаемая ширина — **1024px**. Мобильная адаптивность — отдельный этап, будет реализован позже.

Ключевые брейкпоинты (для текущего уровня поддержки):

| Брейкпоинт | Поведение                                              |
|------------|--------------------------------------------------------|
| `≤ 980px`  | detail-layout → 1 колонка, sidebar вверх               |
| `≤ 768px`  | fields-grid → 1 колонка; toolbar переносится           |
| `≤ 560px`  | navbar → column; flash смещается ниже                  |

---

## 18. Иконки

### Спецификация

Все иконки — inline SVG. Единый стиль:

| Параметр        | Значение                           |
|-----------------|------------------------------------|
| Размер (таблицы)| 16×16px                            |
| Размер (кнопки) | 20×20px                            |
| `stroke`        | `currentColor`                     |
| `stroke-width`  | `1.2`                              |
| `fill`          | `none`                             |
| `stroke-linecap`| `round`                            |
| `stroke-linejoin`| `round`                           |
| `viewBox`       | `0 0 24 24`                        |

### Источник

Набор — **Lucide** (https://lucide.dev). При необходимости новой иконки — брать из Lucide, не рисовать с нуля. Если в Lucide нет подходящей — рисовать по спецификации выше.

### Подключение

Inline SVG прямо в шаблоне. Не использовать `<img>` для иконок (нет контроля цвета через `currentColor`). Не создавать SVG-спрайты — для текущего масштаба проекта inline проще и надёжнее.

### Правила

- Иконка **без текста** — обязателен `title` или `aria-label` для доступности
- Иконка **с текстом рядом** — добавить `aria-hidden="true"` к SVG
- Цвет иконки наследуется от родительского `color` через `currentColor`

---

## 19. Состояния загрузки

### Отправка форм

При нажатии кнопки отправки — визуальная обратная связь через `data-loading-text`:

```html
<button class="tms-btn tms-btn-primary" data-loading-text="Сохранение...">
    Сохранить
</button>
```

```javascript
// static/js/base.js
document.querySelectorAll("form").forEach(form => {
    form.addEventListener("submit", () => {
        const btn = form.querySelector("[data-loading-text]");
        if (btn) {
            btn.disabled = true;
            btn.textContent = btn.dataset.loadingText;
        }
    });
});
```

**Правило**: каждая кнопка отправки формы должна иметь `data-loading-text`.

### Partial-загрузка контента (таблицы, списки)

Во время fetch-запроса (поиск, сортировка, пагинация) показывать, что контент обновляется:

```css
[data-list-content].is-loading {
    opacity: 0.5;
    pointer-events: none;
    transition: opacity 0.15s ease;
}
```

```javascript
// Перед запросом
container.classList.add('is-loading');

// После получения ответа
container.innerHTML = html;
container.classList.remove('is-loading');
```

Не использовать skeleton-loader или spinner для partial-обновлений — достаточно приглушения контента. Skeleton уместен только при первой загрузке страницы, если контент грузится асинхронно (в текущем проекте таких случаев нет).

---

## 20. Обработка ошибок

### В формах

Описано в разделе 12: `.errorlist` под полями, `.form-errors` наверху формы.

### При fetch-запросах (Partial HTML, cascading selects, AJAX-формы)

Три сценария:

**1. Сетевая ошибка** (fetch упал, нет соединения):

```javascript
catch (error) {
    if (error.name === 'AbortError') return; // отменённый запрос — не ошибка
    container.innerHTML = `
        <div class="alert alert-error">
            Не удалось загрузить данные.
            <button type="button" class="tms-btn tms-btn-secondary tms-btn-sm"
                    onclick="location.reload()">Обновить</button>
        </div>`;
}
```

**2. Ошибка авторизации** (сессия истекла, 401/403):

```javascript
if (resp.status === 401 || resp.status === 403) {
    location.href = '/accounts/login/?next=' + encodeURIComponent(location.pathname);
    return;
}
```

**3. Серверная ошибка** (500):

```javascript
if (!resp.ok) {
    container.innerHTML = `
        <div class="alert alert-error">
            Произошла ошибка на сервере. Попробуйте обновить страницу.
        </div>`;
    return;
}
```

**Правило**: каждый `fetch` в проекте должен обрабатывать все три сценария. Необработанный fetch — техдолг.

---

## 21. Известные проблемы и технический долг

### 🔴 Высокий приоритет

**1. Дублирование `{% if messages %}` в шаблонах**

Решение: проверить все шаблоны, удалить inline-блоки messages. Шаблон `trip_detail.html` уже исправлен.

```bash
grep -r "{% if messages %}" templates/
```

---

**2. Инлайн-стили в шаблонах**

В ряде мест используются `style="..."` прямо в HTML. Это делает поддержку сложной. Всё что повторяется более одного раза — выносить в CSS-класс.

---

**3. Слишком много вариаций font-size**

Сейчас в коде 16+ уникальных значений от `0.7rem` до `1.05rem`. Привести к CSS-переменным `--text-xs` ... `--text-xl` из раздела 2.

---

### 🟡 Средний приоритет

**4. Дублирование карточечных компонентов**

- `.card` vs `.page-card` — одно и то же → унифицировать в `.card`
- `.kv-grid`/`.kv` vs `.info-grid`/`.info-item` — одно и то же → унифицировать в `.kv-grid`
- `.fin-badge` vs `.wl-status` vs `.badge` — схожая семантика → переводить на `.status-badge` (раздел 11)

---

**5. Z-index magic numbers**

Перевести все z-index в CSS-переменные из раздела 2. Grep для поиска:

```bash
grep -rn "z-index" static/
```

---

**6. Fetch без обработки ошибок**

Проверить все `fetch()` в JS-файлах на соответствие паттерну из раздела 20.

---

### 🟢 Низкий приоритет

**7. Фокус и доступность**

Базовый focus-ring настроен:
```css
outline: 3px solid rgba(37, 99, 235, 0.3);
```
Но не все интерактивные кастомные элементы (dropdown-пункты, toggle) проходят проверку по доступности. При критичных пользовательских действиях добавлять `aria-label`, `role`, `tabindex`.

---

## 22. Быстрый справочник

| Задача                              | Решение                                              |
|-------------------------------------|------------------------------------------------------|
| Показать уведомление после действия | `messages.success(request, "...")` в view            |
| Не прокручивать страницу после POST | Якорь `#id` + `redirect(url + "#id")`                |
| Новая секция с данными              | `.section` + `.section-title` + `.kv-grid`           |
| Новая форма                         | `.form-card` + `.section` + `.fields-grid` + `.field`|
| Статус объекта                      | `.status-badge status-badge--{семантика}`            |
| Пустой список                       | `.empty-state`                                       |
| Постоянный алерт на странице        | `.alert alert-{тип}`                                 |
| Кнопка основного действия           | `.tms-btn tms-btn-primary` (одна на страницу)        |
| Кнопки вторичных действий           | `.tms-btn tms-btn-secondary`                         |
| Деструктивное действие              | `.tms-btn tms-btn-danger` (только в confirm/модалке) |
| Новая списковая страница            | `.ENTITY-page` > `.list-toolbar` + `.table-card`     |
| Подтверждение удаления              | `.confirm-inline` с двумя кнопками (не `confirm()`)  |
| Модалка подтверждения               | `.modal-overlay` + `.modal-dialog` + `data-modal-open` |
| Модалка с формой                    | `.modal-dialog--wide` + `.modal-fields` + `.modal-field` |
| Hover/focus-переход                 | `transition: 0.15s ease`                             |
| Зависимые поля                      | `data-cascade-source` + `data-cascade-target` (раздел 12) |
| Состояние загрузки кнопки           | `data-loading-text` на `<button>` (раздел 19)        |
| Загрузка partial-контента           | `.is-loading` на контейнере (раздел 19)              |
| Ошибка fetch                        | `.alert alert-error` в контейнере (раздел 20)        |
| Размер шрифта                       | Только `--text-xs` ... `--text-xl` (раздел 2)        |
| Z-index                             | Только `--z-*` переменные (раздел 2)                 |
| Новая иконка                        | Lucide, inline SVG, спецификация в разделе 18        |