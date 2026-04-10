# Стандарт списковой страницы

> Эталонная реализация: **Список счетов** (`invoicing/invoice_list.html`).
> Все новые списковые страницы создаются по этому стандарту.
> Существующие страницы приводятся к нему при рефакторинге.

---

## Архитектура: файлы и их роли

```
<app>/
  views.py                                    # View с partial-рендерингом
  templates/<app>/
    <entity>_list.html                        # Основной шаблон (toolbar + include)
    <entity>_list_table.html                  # Partial (таблица + pagination footer)
  static/<app>/
    css/<entity>_list.css                     # Стили страницы
    js/<entity>_list.js                       # Логика фильтров, AJAX, history
```

Глобальные компоненты (не дублировать в app-стилях):
- `static/css/tables.css` — `.search-field-wrap`, `.tms-table`, `.pagination`, `.row-actions`, `.empty-state`
- `static/css/globals.css` — `.modal-*`, `.alert`, `.status-badge`

---

## 1. View (Python)

### Наследование

```python
class EntityListView(UserOwnedListView):
    model = Entity
    template_name = "<app>/<entity>_list.html"
    partial_template_name = "<app>/<entity>_list_table.html"
    context_object_name = "<entities>"
    paginate_by = 25
    page_size_options = [25, 50, 100]
```

`UserOwnedListView` (`transdoki/views.py`) уже содержит:
- Tenant-фильтрацию по `account`
- `get_paginate_by()` с поддержкой `page_size` из GET
- `_build_pagination_items()` — умная пагинация с ellipsis

### Partial-рендеринг

Один view, два режима:

```python
def get_template_names(self):
    if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return [self.partial_template_name]
    return [self.template_name]
```

### Фильтры в get_queryset

Каждый фильтр — отдельный метод `_apply_*`:

```python
def get_queryset(self):
    qs = super().get_queryset().select_related(...)
    qs = self._apply_search(qs)
    qs = self._apply_date_filters(qs)
    return qs.order_by("-date", "-pk")

def _apply_search(self, qs):
    q = self.request.GET.get("q", "").strip()
    if not q:
        return qs
    return qs.filter(
        Q(number__icontains=q) | Q(customer__short_name__icontains=q)
    )

def _apply_date_filters(self, qs):
    date_from = (self.request.GET.get("date_from") or "").strip() or None
    date_to = (self.request.GET.get("date_to") or "").strip() or None
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs
```

### get_context_data

Обязательные ключи:

```python
def get_context_data(self, **kwargs):
    ctx = super().get_context_data(**kwargs)

    page_obj = ctx.get("page_obj")
    ctx["pagination_items"] = (
        self._build_pagination_items(page_obj) if page_obj else []
    )
    ctx["page_size_options"] = self.page_size_options

    current_page_size = self.get_paginate_by(self.object_list)

    # filters — текущие значения для шаблона
    ctx["filters"] = {
        "q": (self.request.GET.get("q") or "").strip(),
        "date_from": (self.request.GET.get("date_from") or "").strip(),
        "date_to": (self.request.GET.get("date_to") or "").strip(),
        "page_size": str(current_page_size),
    }

    # query_string — для pagination-ссылок (без page, без дефолтов)
    base_params = {}
    if ctx["filters"]["q"]:
        base_params["q"] = ctx["filters"]["q"]
    if ctx["filters"]["date_from"]:
        base_params["date_from"] = ctx["filters"]["date_from"]
    if ctx["filters"]["date_to"]:
        base_params["date_to"] = ctx["filters"]["date_to"]
    if str(current_page_size) != str(self.paginate_by):
        base_params["page_size"] = current_page_size
    ctx["query_string"] = ("&" + urlencode(base_params)) if base_params else ""

    return ctx
```

---

## 2. Основной шаблон (`<entity>_list.html`)

```html
{% extends "base.html" %}
{% load static %}

{% block head %}
<link rel="stylesheet" href="{% static '<app>/css/<entity>_list.css' %}">
{% endblock %}

{% block content %}
<section class="<entity>s-page">

    <form method="get" class="list-toolbar" data-<entity>-filters>

        <div class="toolbar-zone-title">
            <h1>Заголовок</h1>
        </div>

        <div class="toolbar-zone-filters">
            <!-- Поиск (глобальный компонент из tables.css) -->
            <div class="search-field-wrap{% if filters.q %} is-filtered{% endif %}">
                <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24"
                     fill="none" aria-hidden="true">
                    <circle cx="11" cy="11" r="8" stroke="currentColor"
                            stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="m21 21-4.35-4.35" stroke="currentColor"
                          stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <input type="text"
                       name="q"
                       class="search-input"
                       value="{{ filters.q }}"
                       placeholder="Номер или заказчик…"
                       data-filter="q"
                       autocomplete="off">
                <button type="button" class="search-clear"
                        data-search-clear aria-label="Очистить поиск">
                    <svg width="12" height="12" viewBox="0 0 24 24"
                         fill="none" aria-hidden="true">
                        <path d="M18 6L6 18M6 6l12 12" stroke="currentColor"
                              stroke-width="2" stroke-linecap="round"
                              stroke-linejoin="round"/>
                    </svg>
                </button>
            </div>

            <!-- Календарь -->
            <button type="button"
                    class="tms-btn tms-btn-secondary visibility-toggle"
                    data-calendar-toggle
                    aria-expanded="false"
                    title="Фильтр по дате">
                <svg width="16" height="16" viewBox="0 0 24 24"
                     fill="none" aria-hidden="true">
                    <rect x="3" y="4" width="18" height="18" rx="2"
                          stroke="currentColor" stroke-width="1.2"
                          stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M16 2v4M8 2v4M3 10h18"
                          stroke="currentColor" stroke-width="1.2"
                          stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </button>

            <div class="date-range-expand" data-calendar-fields>
                <input type="date"
                       name="date_from"
                       class="filter-input"
                       value="{{ filters.date_from }}"
                       data-filter="date_from">
                <span class="date-range-sep">&mdash;</span>
                <input type="date"
                       name="date_to"
                       class="filter-input"
                       value="{{ filters.date_to }}"
                       data-filter="date_to">
            </div>

            <!-- Дополнительные фильтры (если есть): select, checkbox -->
        </div>

        <!-- Кнопка создания (если есть) -->
        <div class="toolbar-zone-action">
            <a href="{% url '<app>:create' %}"
               class="tms-btn tms-btn-primary tms-btn-add">+ Создать</a>
        </div>

    </form>

    <div data-list-content>
        {% include "<app>/<entity>_list_table.html" %}
    </div>

</section>
{% endblock %}

{% block extra_js %}
<script defer src="{% static '<app>/js/<entity>_list.js' %}"></script>
{% endblock %}
```

### Правила toolbar

| Зона | Класс | Содержимое | Поведение |
|------|-------|------------|-----------|
| Заголовок | `.toolbar-zone-title` | `<h1>` | `flex-shrink: 0`, не сжимается |
| Фильтры | `.toolbar-zone-filters` | Поиск, календарь, даты, доп. фильтры | `flex-wrap: wrap`, `gap: 8px` |
| Действие | `.toolbar-zone-action` | Кнопка создания | `margin-left: auto`, прижата вправо |

Кнопки «Применить» нет. Все фильтры реактивные (AJAX при изменении).

### Toolbar без layout shift

- `align-items: flex-start` — заголовок не прыгает при росте зоны фильтров
- `h1 line-height: 36px` — выравнивание по высоте поля поиска (36px)
- Поля дат: `visibility: hidden / visible` (не `display: none`) — место зарезервировано

---

## 3. Partial-шаблон (`<entity>_list_table.html`)

```html
<div class="table-card">
    <div class="table-wrap">
        <table class="tms-table">
            <thead>
                <tr>
                    <th class="col-name">Название</th>
                    <th class="col-date">Дата</th>
                    <!-- ... -->
                    <th class="col-actions"></th>
                </tr>
            </thead>
            <tbody>
                {% for item in items %}
                <tr data-detail-url="{% url '<app>:detail' item.pk %}">
                    <td data-label="Название">{{ item.name }}</td>
                    <td data-label="Дата">{{ item.date|date:"d.m.Y" }}</td>
                    <!-- ... -->
                    <td class="row-actions-cell">
                        <div class="row-actions">
                            <a href="{% url '<app>:detail' item.pk %}"
                               class="row-action row-action--view" title="Просмотр">
                                <svg width="16" height="16" viewBox="0 0 24 24"
                                     fill="none" aria-hidden="true">
                                    <!-- Lucide Eye -->
                                </svg>
                            </a>
                        </div>
                    </td>
                </tr>
                {% empty %}
                <tr>
                    <td colspan="N">
                        <div class="empty-state">
                            {% if filters.q %}
                                <p>Ничего не найдено</p>
                            {% else %}
                                <p>Записей пока нет</p>
                            {% endif %}
                        </div>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

{% if page_obj and page_obj.paginator.count > 0 %}
<div class="pagination-footer">
    <div class="pagination-footer-left">
        <span class="pagination-meta">
            Показано {{ page_obj.start_index }}&ndash;{{ page_obj.end_index }}
            из {{ page_obj.paginator.count }}
        </span>
    </div>
    <div class="pagination-footer-center">
        {% if page_obj.paginator.num_pages > 1 %}
        <nav class="pagination" aria-label="Пагинация">
            {% if page_obj.has_previous %}
                <a class="pagination-link pagination-nav"
                   href="?page=1{{ query_string }}">&laquo;</a>
                <a class="pagination-link pagination-nav"
                   href="?page={{ page_obj.previous_page_number }}{{ query_string }}">&lsaquo;</a>
            {% else %}
                <span class="pagination-link pagination-nav is-disabled">&laquo;</span>
                <span class="pagination-link pagination-nav is-disabled">&lsaquo;</span>
            {% endif %}

            {% for item in pagination_items %}
                {% if item.type == 'ellipsis' %}
                    <span class="pagination-ellipsis">&hellip;</span>
                {% elif item.current %}
                    <span class="pagination-link is-current">{{ item.number }}</span>
                {% else %}
                    <a class="pagination-link"
                       href="?page={{ item.number }}{{ query_string }}">{{ item.number }}</a>
                {% endif %}
            {% endfor %}

            {% if page_obj.has_next %}
                <a class="pagination-link pagination-nav"
                   href="?page={{ page_obj.next_page_number }}{{ query_string }}">&rsaquo;</a>
                <a class="pagination-link pagination-nav"
                   href="?page={{ page_obj.paginator.num_pages }}{{ query_string }}">&raquo;</a>
            {% else %}
                <span class="pagination-link pagination-nav is-disabled">&rsaquo;</span>
                <span class="pagination-link pagination-nav is-disabled">&raquo;</span>
            {% endif %}
        </nav>
        {% endif %}
    </div>
    <div class="pagination-footer-right">
        <label class="page-size-control">
            <span class="page-size-label">Показывать:</span>
            <select class="page-size-select" data-page-size-select>
                {% for size in page_size_options %}
                    <option value="{{ size }}"
                        {% if filters.page_size == size|stringformat:"s" %}selected{% endif %}>
                        {{ size }}
                    </option>
                {% endfor %}
            </select>
        </label>
    </div>
</div>
{% endif %}
```

### Правила partial

- Обёртка `.table-card > .table-wrap > table.tms-table`
- `<thead>` рендерится всегда (заголовки видны при пустой таблице)
- Пустое состояние — `{% empty %}` внутри `<tbody>`, `<td colspan="N">`
- Если фильтр поиска активен: «Ничего не найдено». Иначе: «Записей пока нет»
- `<tfoot>` с итогами — только при наличии данных (`{% if items %}`)
- `data-detail-url` на `<tr>` — для навигации по клику на строку
- `data-label` на `<td>` — для мобильной адаптации
- Pagination footer — вне `.table-card`, внутри `data-list-content`

---

## 4. JavaScript (`<entity>_list.js`)

### Структура

```javascript
(function () {
    var STORAGE_KEY = 'tms_<entity>s_page_size';
    var DEFAULT_PAGE_SIZE = '25';

    function init() {
        var form = document.querySelector('[data-<entity>-filters]');
        if (!form) return;

        // --- Элементы ---
        var searchInput = form.querySelector('[name="q"]');
        var calendarToggle = form.querySelector('[data-calendar-toggle]');
        var calendarFields = form.querySelector('[data-calendar-fields]');
        var dateFromInput = form.querySelector('[name="date_from"]');
        var dateToInput = form.querySelector('[name="date_to"]');
        var searchWrap = searchInput ? searchInput.closest('.search-field-wrap') : null;
        var searchClear = form.querySelector('[data-search-clear]');
        var pageSizeSelect = document.querySelector('[data-page-size-select]');
        var contentContainer = document.querySelector('[data-list-content]');
        if (!contentContainer) return;

        var fetchController = null;
        var debounceTimer = null;

        // --- buildParams ---
        // --- fetchList ---
        // --- Поиск (debounce 300ms) ---
        // --- Календарь (toggle + syncVisibility) ---
        // --- Доп. фильтры (change → fetchList) ---
        // --- Page size (localStorage + fetchList) ---
        // --- Pagination (делегированный клик) ---
        // --- Form submit (preventDefault → fetchList) ---
        // --- popstate (restoreFormFromParams + fetchList) ---
        // --- Инициализация ---
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
```

### buildParams

Собирает URLSearchParams из текущего состояния формы. Пропускает пустые значения и дефолты:

```javascript
function buildParams(overrides) {
    var params = new URLSearchParams();

    var q = (overrides && 'q' in overrides)
        ? overrides.q
        : (searchInput ? searchInput.value.trim() : '');
    if (q) params.set('q', q);

    var dateFrom = (overrides && 'date_from' in overrides)
        ? overrides.date_from
        : (dateFromInput ? dateFromInput.value.trim() : '');
    if (dateFrom) params.set('date_from', dateFrom);

    var dateTo = (overrides && 'date_to' in overrides)
        ? overrides.date_to
        : (dateToInput ? dateToInput.value.trim() : '');
    if (dateTo) params.set('date_to', dateTo);

    // page_size — только если не дефолт
    var ps = pageSizeSelect ? pageSizeSelect.value : '';
    if (ps && String(ps) !== DEFAULT_PAGE_SIZE) {
        params.set('page_size', ps);
    }

    // page — только через overrides
    if (overrides && overrides.page) {
        params.set('page', overrides.page);
    }

    return params;
}
```

### fetchList

```javascript
function fetchList(params) {
    var qs = params.toString();
    var urlStr = window.location.pathname + (qs ? '?' + qs : '');

    if (fetchController) fetchController.abort();
    fetchController = new AbortController();

    contentContainer.classList.add('is-loading');

    fetch(urlStr, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        signal: fetchController.signal
    })
    .then(function (r) {
        if (r.status === 401 || r.status === 403) {
            location.href = '/accounts/login/?next='
                + encodeURIComponent(location.pathname);
            return;
        }
        if (!r.ok) throw new Error('server_error');
        return r.text();
    })
    .then(function (html) {
        if (!html) return;
        contentContainer.innerHTML = html;
        contentContainer.classList.remove('is-loading');
        bindPageSizeSelect();
        history.pushState(null, '', urlStr);
    })
    .catch(function (err) {
        if (err.name === 'AbortError') return;
        contentContainer.classList.remove('is-loading');
        contentContainer.innerHTML =
            '<div class="alert alert-error">' +
            (err.message === 'server_error'
                ? 'Произошла ошибка на сервере. '
                : 'Не удалось загрузить данные. ') +
            '<button type="button" class="tms-btn tms-btn-secondary tms-btn-sm" ' +
            'onclick="location.reload()">Обновить</button></div>';
    });
}
```

### Поиск

```javascript
function updateSearchState() {
    if (!searchInput || !searchWrap) return;
    searchWrap.classList.toggle('is-filtered', !!searchInput.value.trim());
}

// Ввод — debounce 300ms
searchInput.addEventListener('input', function () {
    updateSearchState();
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function () {
        fetchList(buildParams({ page: '' }));
    }, 300);
});

// Escape — очистка
searchInput.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        searchInput.value = '';
        updateSearchState();
        fetchList(buildParams({ page: '' }));
    }
});

// Кнопка × — очистка
searchClear.addEventListener('click', function () {
    searchInput.value = '';
    updateSearchState();
    fetchList(buildParams({ page: '' }));
    searchInput.focus();
});
```

### Календарь

Поля дат скрыты через `visibility: hidden` (CSS). JS управляет классом `is-visible`.

Логика:
- Клик по иконке — toggle видимости полей
- Подсветка иконки (`aria-expanded="true"`) — если хотя бы одно поле заполнено ИЛИ поля открыты
- При очистке обоих полей — поля автоматически скрываются
- Заполненное поле подсвечивается классом `is-filled`
- Каждое изменение даты (`change` + `input`) — мгновенный fetch

```javascript
var calendarOpen = false;

function hasAnyDate() {
    return !!((dateFromInput && dateFromInput.value)
           || (dateToInput && dateToInput.value));
}

function syncCalendarVisibility() {
    if (hasAnyDate()) {
        calendarOpen = true;
        calendarFields.classList.add('is-visible');
    } else {
        calendarOpen = false;
        calendarFields.classList.remove('is-visible');
    }
    updateCalendarToggleState();
}

// Toggle по клику на иконку
calendarToggle.addEventListener('click', function (e) {
    e.stopPropagation();
    if (calendarOpen) {
        calendarOpen = false;
        calendarFields.classList.remove('is-visible');
        updateCalendarToggleState();
    } else {
        openCalendarFields();
        // Фокус на первое пустое поле
    }
});

// Изменение даты → sync + fetch
function onDateChange() {
    syncCalendarVisibility();
    fetchList(buildParams({ page: '' }));
}
```

### Дополнительные фильтры

Select, checkbox и другие — мгновенный fetch при `change`:

```javascript
if (directionSelect) {
    directionSelect.addEventListener('change', function () {
        fetchList(buildParams());
    });
}
```

### Пагинация + page size

```javascript
// Делегированный клик по pagination-link
document.addEventListener('click', function (e) {
    var link = e.target.closest(
        '[data-list-content] .pagination-link:not(.is-current):not(.is-disabled)'
    );
    if (!link) return;
    e.preventDefault();
    var params = new URLSearchParams(link.getAttribute('href').split('?')[1] || '');
    fetchList(params);
});

// Page size — сохранение в localStorage
function bindPageSizeSelect() {
    pageSizeSelect = document.querySelector('[data-page-size-select]');
    if (!pageSizeSelect) return;
    pageSizeSelect.addEventListener('change', function () {
        localStorage.setItem(STORAGE_KEY, pageSizeSelect.value);
        fetchList(buildParams({ page: '' }));
    });
}
```

### popstate (кнопка «Назад»)

```javascript
window.addEventListener('popstate', function () {
    var params = new URLSearchParams(window.location.search);
    restoreFormFromParams(params);
    fetchList(params);
});

function restoreFormFromParams(params) {
    if (searchInput) searchInput.value = params.get('q') || '';
    if (dateFromInput) dateFromInput.value = params.get('date_from') || '';
    if (dateToInput) dateToInput.value = params.get('date_to') || '';
    // ... доп. фильтры
    updateSearchState();
    syncCalendarVisibility();
}
```

---

## 5. CSS (`<entity>_list.css`)

### Что определяется в app-стилях

```css
/* Обёртка страницы */
.<entity>s-page {
    display: flex;
    flex-direction: column;
    gap: 10px;
    width: 100%;
    min-width: 0;
    margin: 0;
}

/* Toolbar */
.<entity>s-page .list-toolbar {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    flex-shrink: 0;
}

.<entity>s-page .list-toolbar h1 {
    margin: 0;
    font-size: clamp(1.25rem, 1.8vw, 1.5rem);
    line-height: 36px;
    letter-spacing: -0.01em;
    white-space: nowrap;
}

.<entity>s-page .toolbar-zone-title { flex-shrink: 0; }

.<entity>s-page .toolbar-zone-filters {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

.<entity>s-page .toolbar-zone-action {
    flex-shrink: 0;
    margin-left: auto;
}

/* Кнопка-тоггл календаря */
.<entity>s-page .visibility-toggle { ... }
.<entity>s-page .visibility-toggle:hover { ... }
.<entity>s-page .visibility-toggle[aria-expanded="true"] { ... }

/* Поля дат */
.<entity>s-page .filter-input { ... }
.<entity>s-page .date-range-expand { visibility: hidden; pointer-events: none; }
.<entity>s-page .date-range-expand.is-visible { visibility: visible; pointer-events: auto; }
.<entity>s-page .date-range-expand .filter-input.is-filled { border-color: var(--primary); background: var(--hover-active); }
.<entity>s-page .date-range-expand .filter-input { width: 150px; }

/* Контейнер данных */
[data-list-content] { display: flex; flex-direction: column; gap: 14px; }
[data-list-content].is-loading { opacity: 0.5; pointer-events: none; transition: opacity 0.15s ease; }

/* Ширины колонок (table-layout: fixed) */
.col-name   { width: 250px; }
.col-date   { width: 110px; }
.col-amount { width: 120px; }
.col-actions { width: 90px; }
```

### Что НЕ определяется в app-стилях (берётся из tables.css)

- `.search-field-wrap`, `.search-icon`, `.search-input`, `.search-clear`
- `.tms-table`, `thead th`, `tbody td`
- `.row-actions`, `.row-action`, `.row-action--view`
- `.pagination`, `.pagination-link`, `.pagination-footer`
- `.page-size-control`, `.page-size-select`
- `.empty-state`
- `.sortable-header`

---

## 6. Чек-лист при создании новой списковой страницы

### View
- [ ] Наследует `UserOwnedListView`
- [ ] `partial_template_name` задан
- [ ] `get_template_names()` — AJAX → partial, обычный → full
- [ ] Каждый фильтр — отдельный метод `_apply_*`
- [ ] `context["filters"]` содержит все текущие значения фильтров
- [ ] `context["query_string"]` — для pagination-ссылок (без пустых значений и дефолтов)
- [ ] `context["pagination_items"]` — от `_build_pagination_items`
- [ ] `context["page_size_options"]` — для select

### Основной шаблон
- [ ] `<form class="list-toolbar" data-<entity>-filters>` — toolbar = form
- [ ] `toolbar-zone-title` + `toolbar-zone-filters` + `toolbar-zone-action`
- [ ] Поиск — `search-field-wrap` с `search-icon`, `search-input`, `search-clear`
- [ ] Календарь — `visibility-toggle[data-calendar-toggle]` + `.date-range-expand[data-calendar-fields]`
- [ ] `<div data-list-content>{% include partial %}</div>`
- [ ] JS подключён в `{% block extra_js %}`
- [ ] Нет кнопки «Применить» — всё реактивное
- [ ] Одна `tms-btn-primary` на странице

### Partial-шаблон
- [ ] `.table-card > .table-wrap > table.tms-table`
- [ ] `<thead>` рендерится всегда
- [ ] `{% empty %}` внутри `<tbody>` с `colspan`
- [ ] Пустое состояние: «Ничего не найдено» при поиске, «Записей пока нет» без фильтров
- [ ] `data-detail-url` на `<tr>` для навигации
- [ ] `data-label` на `<td>` для мобилки
- [ ] Pagination footer — вне `.table-card`, внутри `data-list-content`

### JavaScript
- [ ] IIFE, `init()` вызывается на DOMContentLoaded
- [ ] `buildParams()` — пропускает пустые значения и дефолты
- [ ] `fetchList()` — AbortController, is-loading, три типа ошибок (сеть, 401/403, сервер)
- [ ] Поиск — debounce 300ms, Escape для очистки, кнопка ×
- [ ] Календарь — toggle, syncVisibility, is-filled на заполненных полях
- [ ] Доп. фильтры — мгновенный fetch при change
- [ ] `history.pushState` после каждого fetch
- [ ] `popstate` — восстановление формы + fetch
- [ ] `bindPageSizeSelect` — localStorage + fetch
- [ ] Form submit — `preventDefault`, не перезагрузка

### CSS
- [ ] Scope через `.<entity>s-page` — не загрязнять глобальные стили
- [ ] Не дублировать стили из `tables.css`
- [ ] `align-items: flex-start` на toolbar — без layout shift
- [ ] `h1 line-height: 36px` — выравнивание с полем поиска
- [ ] Даты — `visibility: hidden` (не `display: none`)
- [ ] `[data-list-content].is-loading` — приглушение при загрузке
- [ ] Все `font-size` через CSS-переменные
- [ ] Все `z-index` через `--z-*`

### Иконки
- [ ] Все SVG: `viewBox="0 0 24 24"`, `stroke-width="1.2"`, `fill="none"`, `stroke="currentColor"`
- [ ] Размер: 16×16 в таблицах, 14×14 для лупы, 12×12 для крестика
- [ ] `aria-hidden="true"` на декоративных, `aria-label` или `title` на кнопках без текста
