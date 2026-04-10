# Аудит модальных окон — transdoki

**Дата**: 2026-04-10

## Инвентаризация

Найдено **18 модальных окон** + **3 inline-подтверждения**.

| Тип | Кол-во | Примеры |
|-----|--------|---------|
| Формы создания | 8 | Платёж, ТС, водитель, банк. счёт, контакт, quick-create (орг/лицо/ТС) |
| Формы редактирования | 2 | Банк. счёт, контакт |
| Подтверждения удаления | 7 | ТС, водитель, банк. счёт, контакт, вложение, счёт |
| Специальные | 1 | Добавление пользователя (cabinet) |
| Inline-подтверждения | 3 | statement_table, settlement_detail, template_settings |

---

## Выполненные шаги

### Шаг 1. modal-helpers.js (выполнено)
Создан `static/js/modal-helpers.js` — общая библиотека (`window.ModalHelpers`), подключена в `base.html` перед `base.js`.

Извлечены функции: `clearErrors`, `showFieldError`, `showGeneralError`, `applyFieldErrors`, `setupResetOnClose`, `setSubmitting`, `escapeHtml`.

### Шаг 2. Рефакторинг потребителей (выполнено)

| Файл | До | После |
|------|-----|-------|
| person_create_modal.js | 115 | 52 |
| vehicle_create_modal.js | 116 | 53 |
| contact_create_modal.js | 262 | 152 |
| bank_account_create_modal.js | 312 | 233 |
| bank_account_edit_modal.js | 378 | 277 |
| quick_create.js | 308 | 308 (не тронут — data-err паттерн) |

### Шаг 3. Унификация cabinet (выполнено)
- `.modal-box` → `.modal-dialog`, `.modal-btn-*` → `.tms-btn-*`, `.au-*` → `.modal-field`
- `style.display` → `hidden` атрибут
- Кнопка открытия → `data-modal-open`, отмена → `data-modal-close`
- Удалены 65 строк кастомного CSS из cabinet.css
- Удалены кастомные обработчики ESC и overlay click
- `style.borderColor = "#ef4444"` → `.is-invalid` класс
- Сброс при закрытии через MutationObserver (при `hidden = true`), корректно работает с двухшаговым credentials-флоу

### Шаг 4a. Accessibility — aria-атрибуты (выполнено)
В `base.js` добавлены `openModal()` / `closeModal()`:
- `role="dialog"` + `aria-modal="true"` при открытии
- `aria-labelledby` с привязкой к `.modal-title`
- Фокус на первый интерактивный элемент при открытии
- Возврат фокуса на триггер при закрытии

### Шаг 6. Документация (выполнено)
Дополнен `docs/ui-guide.md` (раздел 4 «Модальные окна»):
- API ModalHelpers с таблицей методов
- Полный JS-пример AJAX-формы в модалке
- data-err паттерн: когда и зачем
- Программное открытие модалки
- Accessibility, responsive, скролл длинных форм
- Запрет кастомных `.modal-*` классов
- Быстрый справочник обновлён

---

## Оставшиеся задачи

### Шаг 4b. Focus trap
**Приоритет**: средний. **Риск**: высокий при некачественной реализации.

Удержание Tab внутри открытой модалки (WCAG 2.1, критерий 2.1.2). Нетривиальные edge cases:
- Disabled-элементы и `tabindex="-1"` не должны попадать в цикл
- Динамически добавляемые поля (bank_account: переключение search → manual mode)
- Мобильные клавиатуры и виртуальный Tab
- Модалки без фокусируемых элементов (подтверждения удаления — только кнопки)

**Рекомендация**: реализовать как отдельную задачу с ручным тестированием на реальных модалках. Не совмещать с другими изменениями.

### Шаг 5a. CSS fade-in/out анимация
**Приоритет**: низкий. **Риск**: минимальный.

Модалки появляются мгновенно. Плавное появление (200ms fade) улучшает восприятие.

Ориентировочная реализация в `globals.css`:
```css
.modal-overlay {
    opacity: 0;
    transition: opacity 0.2s ease;
    pointer-events: none;
}
.modal-overlay:not([hidden]) {
    opacity: 1;
    pointer-events: auto;
}
```

Нюанс: `hidden` устанавливает `display: none`, что отменяет transition. Может потребоваться переход на класс `.is-open` вместо `hidden` — это затронет `base.js`, `modal-helpers.js` (setupResetOnClose) и все MutationObserver'ы. Нужна оценка трудозатрат перед реализацией.

### Шаг 5b. DOM-update вместо location.reload()
**Приоритет**: низкий. **Риск**: средний (много точек изменений).

Сейчас после успешного создания/удаления через модалку — `location.reload()`. Страница моргает, скролл сбрасывается.

Где актуально (детальные страницы с коллекциями):
- `organization_detail`: ТС, водители, банк. счета, контакты — 8 модалок
- `trip_detail`: вложения (уже реализовано через DOM-update)

**Объём работы**: для каждой модалки — view должен возвращать данные нового/изменённого объекта в JSON, JS должен вставить/обновить/удалить DOM-элемент. ~8 пар view+JS.

**Рекомендация**: делать инкрементально, по одной модалке за раз. Начать с delete-модалок (проще — только удалить элемент из DOM). Create/edit — сложнее (нужно строить HTML нового элемента).

### Дублирование dropdown-логики в bank_account
**Приоритет**: низкий. **Риск**: минимальный.

`bank_account_create_modal.js` и `bank_account_edit_modal.js` содержат идентичные функции: `showDropdown`, `selectBank`, `resetBankSelection`, обработчики keyboard nav, debounce-поиск. Суммарно ~100 строк дублирования.

Вариант: извлечь в `static/organizations/js/bank_suggest.js` — общий модуль подсказок банков.

### quick_create.js → ModalHelpers (опционально)
**Приоритет**: низкий. **Риск**: средний.

`quick_create.js` использует data-err паттерн (статические элементы ошибок). `ModalHelpers.clearErrors()` удаляет `.modal-field-error` из DOM — несовместимо.

Варианты:
- A. Оставить как есть (текущее решение) — код не дублируется, работает стабильно
- B. Добавить в ModalHelpers альтернативный `clearStaticErrors(form)` который очищает textContent, не удаляя элементы. Переводить quick_create и cabinet на него

Вариант A предпочтителен до появления третьего файла с data-err паттерном.
