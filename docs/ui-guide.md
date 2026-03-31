# transdoki — UI/UX Guide

> Живой документ. Обновлять при добавлении новых компонентов или изменении паттернов.

---

## 1. Принципы

- **Минимализм без потери функциональности** — каждый элемент должен быть оправдан
- **Предсказуемость** — одинаковые сущности выглядят одинаково везде
- **Не прерывать пользователя** — после действий (сохранение, фиксация) держать его в контексте, а не кидать наверх страницы
- **Иерархия через типографику и отступы**, не через цвет

---

## 2. Токены (CSS-переменные)

Все значения берутся из `:root` в `base.html`. Не использовать хардкод там, где есть переменная.

```css
/* Цвета */
--bg: #f6f7fb          /* фон страницы */
--surface: #ffffff     /* поверхность карточек */
--text: #111827        /* основной текст */
--muted: #6b7280       /* второстепенный текст */
--border: #e5e7eb      /* линии и рамки */

/* Акцент */
--primary: #2563eb
--primary-hover: #1d4ed8

/* Геометрия */
--radius: 12px         /* основной radius */
--radius-sm: 10px
--shadow: 0 8px 24px rgba(15, 23, 42, 0.06)
--container: 1200px
```

### Семантическая палитра состояний

| Состояние   | Текст       | Фон       | Рамка     |
|-------------|-------------|-----------|-----------|
| success     | `#16a34a`   | `#f0fdf4` | `#bbf7d0` |
| warning     | `#d97706`   | `#fffbeb` | `#fde68a` |
| error       | `#dc2626`   | `#fef2f2` | `#fecaca` |
| info        | `#2563eb`   | `#eff6ff` | `#bfdbfe` |
| neutral     | `#6b7280`   | `#f3f4f6` | `#e5e7eb` |

---

## 3. Типографика

Шрифт: **Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif**

### Шкала размеров (использовать только эти значения)

| Роль                        | Размер     | Weight |
|-----------------------------|------------|--------|
| Заголовок страницы (полная ширина) | `clamp(1.25rem, 1.8vw, 1.7rem)` | 700 |
| Заголовок карточки / компонента | `1.4rem` | 700 |
| Заголовок секции            | `0.98rem`  | 700    |
| Тело / значения             | `0.95rem`  | 400    |
| Метки форм, kv-label        | `0.82–0.9rem` | 600 |
| Вспомогательный текст       | `0.84rem`  | 400    |
| Мелкие бейджи, хедеры таблиц| `0.75–0.78rem` | 600–700 |

`clamp()` — только для заголовков в полноширинном контексте (списки, детальные страницы). Для компонентов с фиксированной шириной (карточки, модалки, формы) — фиксированный `rem`.

> ⚠️ **Проблема**: в проекте сейчас 16+ разных font-size — от 0.7rem до 1.05rem с шагом 0.01–0.02rem. Это даёт визуальный шум. При создании новых шаблонов строго придерживаться таблицы выше.

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
| `tms-btn-fix`        | Фиксация/подтверждение финансовых данных (зелёный)         |
| `tms-btn-add`        | Добавить строку, добавить элемент (иконка +)               |
| `tms-btn-sm`         | Кнопки внутри таблиц и компактных блоков                   |

**Правило**: не более одной `tms-btn-primary` в видимой области. Остальные — secondary или light.

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

`base.html` автоматически рендерит их как фиксированный toast вверху экрана (позиция `fixed`, z-index 70). Success и info скрываются через 4 секунды, error/warning — по клику.

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

---

## 7. Статические файлы (CSS и JS)

Стили и скрипты — только во внешних файлах, подключаемых через `{% static %}`. Инлайн `<style>` и `<script>` в шаблонах запрещены. Это Django-way: файлы кешируются браузером и корректно подхватываются `collectstatic`.

### Структура

```
static/
  css/forms.css        # общие компоненты форм (.field, .errorlist, .helptext, .form-errors)
  css/nav.css          # навбар
  css/tables.css       # таблицы
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

Не использовать произвольные числа. Таблица слоёв:

| Значение | Назначение                                   |
|----------|----------------------------------------------|
| 0        | базовый контент                              |
| 20       | sticky ячейки таблицы (td actions)           |
| 30       | sticky заголовки таблицы                     |
| 40       | sticky заголовок колонки actions             |
| 50       | navbar                                        |
| 70       | flash-wrap (toast уведомления)               |
| 200      | inline-дропдауны внутри форм (подсказки ИНН) |
| 1000     | модальные overlay                            |
| 1100     | autocomplete-dropdown в полях (trips/waybills) |
| 1200     | filter-dropdown-panel                        |
| 1300     | visibility-panel (настройка колонок)         |
| 1400     | actions-menu (dropdown в таблице)            |

---

## 9. Карточки и структура страниц

### Основная карточка

```html
<div class="card">
    <!-- контент -->
</div>
```

`card` = `page-card` по семантике — **использовать единый класс `card`**.

> ⚠️ **Проблема**: в проекте сосуществуют `.card` и `.page-card` с почти идентичными стилями. При рефакторинге унифицировать в `.card`.

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

> ⚠️ **Проблема**: параллельно существует `.info-grid` / `.info-item` (waybill_detail) с тем же назначением. При рефакторинге привести к `.kv-grid`.

---

## 11. Бейджи статусов

### Финансовые статусы рейса

```html
<span class="fin-badge fin-badge--open">Открыт</span>
<span class="fin-badge fin-badge--calculated">Зафиксирован</span>
<span class="fin-badge fin-badge--invoiced">Документы выставлены</span>
<span class="fin-badge fin-badge--paid">Оплачен</span>
```

### Статусы путевых листов

```html
<span class="wl-status wl-status--open">Открыт</span>
<span class="wl-status wl-status--closed">Закрыт</span>
```

### Баланс в навбаре

Автоматически проставляется через контекст-процессор. Классы: `.balance-ok`, `.balance-warn`, `.balance-danger`, `.balance-exempt`.

> ⚠️ **Проблема**: три разных системы бейджей (`.fin-badge`, `.wl-status`, `.badge` в timeline) с похожей семантикой, но разными реализациями. Новые статусы создавать на основе `.fin-badge` как наиболее полной.

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
- На мобилке (`≤ 768px`) все поля возвращаются в `width: 100%`.

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
- Заголовки: uppercase, `0.78rem`, `--muted` цвет
- Ячейки: `0.89rem`, строки с `cursor: grab` для drag-scroll
- Hover строк: `#f8fafc`

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
- `.row-action` — 28×28px, иконка 16×16px SVG (`stroke="currentColor"`, `stroke-width="1.2"`, `fill="none"`, `round` caps/joins)
- Цвета hover: `--view` синий, `--copy` зелёный, `--print` синий
- Docs-dropdown: меню переносится в `body` (обход `overflow: hidden`), `position: fixed`, умное позиционирование, плавное появление (0.15s)
- При открытом меню строка подсвечивается `#eef6ff`

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

Проект ориентирован на desktop (B2B, работа за ПК). Мобильная адаптивность — желательная, но не приоритетная. Ключевые брейкпоинты:

| Брейкпоинт | Поведение                                              |
|------------|--------------------------------------------------------|
| `≤ 980px`  | detail-layout → 1 колонка, sidebar вверх               |
| `≤ 768px`  | fields-grid → 1 колонка; toolbar переносится           |
| `≤ 560px`  | navbar → column; flash смещается ниже                  |
| `≤ 760px`  | уменьшение padding карточек; кнопки actions на всю ширину |

---

## 18. Известные проблемы и технический долг

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

Сейчас в коде 16+ уникальных значений от `0.7rem` до `1.05rem`. Привести к шкале из раздела «Типографика».

---

### 🟡 Средний приоритет

**4. Дублирование карточечных компонентов**

- `.card` vs `.page-card` — одно и то же
- `.kv-grid`/`.kv` vs `.info-grid`/`.info-item` — одно и то же
- `.fin-badge` vs `.wl-status` vs `.badge` — схожая семантика, разные реализации

Решение: при рефакторинге шаблонов унифицировать. Новый код писать только через `.card` и `.kv-grid`.

---

**5. Отсутствие состояния загрузки при отправке форм**

После нажатия кнопки «Сохранить» нет визуальной обратной связи. При медленном соединении пользователь может нажать повторно.

Решение: добавить `data-loading` паттерн:

```html
<button class="tms-btn tms-btn-primary" data-loading-text="Сохранение...">
    Сохранить
</button>
```

```javascript
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

---

**6. Z-index без системы**

Magic numbers вроде `z-index: 1400` разбросаны по CSS. Перевести в переменные:

```css
:root {
    --z-sticky-cell:    20;
    --z-sticky-header:  30;
    --z-navbar:         50;
    --z-toast:          70;
    --z-modal:          1000;
    --z-dropdown:       1200;
    --z-column-panel:   1300;
    --z-actions-menu:   1400;
}
```

---

### 🟢 Низкий приоритет / к рассмотрению

---

**8. Фокус и доступность**

Базовый focus-ring настроен:
```css
outline: 3px solid rgba(37, 99, 235, 0.3);
```
Но не все интерактивные кастомные элементы (dropdown-пункты, toggle) проходят проверку по доступности. При критичных пользовательских действиях добавлять `aria-label`, `role`, `tabindex`.

---

## 19. Быстрый справочник

| Задача                              | Решение                                              |
|-------------------------------------|------------------------------------------------------|
| Показать уведомление после действия | `messages.success(request, "...")` в view            |
| Не прокручивать страницу после POST | Якорь `#id` + `redirect(url + "#id")`                |
| Новая секция с данными              | `.section` + `.section-title` + `.kv-grid`           |
| Новая форма                         | `.form-card` + `.section` + `.fields-grid` + `.field`|
| Статус объекта                      | `.fin-badge fin-badge--{статус}`                     |
| Пустой список                       | `.empty-state`                                       |
| Постоянный алерт на странице        | `.alert alert-{тип}`                                 |
| Кнопка основного действия           | `.tms-btn tms-btn-primary` (одна на страницу)        |
| Кнопки вторичных действий           | `.tms-btn tms-btn-secondary`                         |
| Новая списковая страница            | `.ENTITY-page` > `.list-toolbar` + `.table-card`     |
| Деструктивное действие              | `.confirm-inline` с двумя кнопками (не `confirm()`)  |
| Модалка подтверждения               | `.modal-overlay` + `.modal-dialog` + `data-modal-open` |
| Модалка с формой                    | `.modal-dialog--wide` + `.modal-fields` + `.modal-field` |
| Hover/focus-переход                 | `transition: 0.15s ease`                             |
