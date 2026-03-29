(function () {
    'use strict';

    const input = document.querySelector('[data-grn-mask]');
    const form  = input && input.closest('form');

    if (!input || !form || typeof IMask === 'undefined') return;

    const typeSelect = form.querySelector('[name="vehicle_type"]');

    /* ──────────────────────────────────────────────
       1. ЛАТИНИЦА → КИРИЛЛИЦА
       ────────────────────────────────────────────── */
    const LAT_TO_CYR = {
        'A': 'А', 'B': 'В', 'E': 'Е', 'K': 'К', 'M': 'М',
        'H': 'Н', 'O': 'О', 'P': 'Р', 'C': 'С', 'T': 'Т',
        'Y': 'У', 'X': 'Х',
    };

    function prepareChar(ch) {
        ch = ch.toUpperCase();
        return LAT_TO_CYR[ch] || ch;
    }

    /* ──────────────────────────────────────────────
       2. КОНФИГУРАЦИИ МАСОК
       ────────────────────────────────────────────── */
    const CYR_REGEX = /[АВЕКМНОРСТУХ]/;

    // Грузовик / Тягач: А 000 ВЕ 00[0]
    const TRUCK_OPTS = {
        mask:            'L 000 LL 00[0]',
        definitions:     { 'L': CYR_REGEX },
        prepareChar:     prepareChar,
        lazy:            true,
        placeholderChar: '_',
        overwrite:       'shift',
    };

    // Прицеп: АВ 0000 00[0]
    const TRAILER_OPTS = {
        mask:            'LL 0000 00[0]',
        definitions:     { 'L': CYR_REGEX },
        prepareChar:     prepareChar,
        lazy:            true,
        placeholderChar: '_',
        overwrite:       'shift',
    };

    /* ──────────────────────────────────────────────
       3. СОЗДАНИЕ / ПЕРЕСОЗДАНИЕ МАСКИ
       ────────────────────────────────────────────── */
    let mask = null;
    let touched = false;
    let blurTimer = null;

    function getOpts() {
        if (typeSelect && typeSelect.value === 'trailer') return TRAILER_OPTS;
        return TRUCK_OPTS;
    }

    function getMinLen() {
        return (typeSelect && typeSelect.value === 'trailer') ? 7 : 8;
    }

    function getMaxLen() {
        return (typeSelect && typeSelect.value === 'trailer') ? 8 : 9;
    }

    function createMask() {
        const raw = mask ? mask.unmaskedValue : input.value.replace(/\s/g, '');
        if (mask) mask.destroy();

        mask = IMask(input, getOpts());

        mask.on('accept', onAccept);

        if (raw) {
            mask.unmaskedValue = raw;
        }
    }

    /* ──────────────────────────────────────────────
       4. ГИДРАТАЦИЯ: сервер отдаёт «А123ВЕ77» без пробелов
       ────────────────────────────────────────────── */
    function hydrateFromServer() {
        const raw = input.value.replace(/\s/g, '');
        if (raw) {
            mask.unmaskedValue = raw;
        }
    }

    /* ──────────────────────────────────────────────
       5. ЭЛЕМЕНТ ОШИБКИ
       ────────────────────────────────────────────── */
    const group = input.closest('.field');
    let errorEl = group && group.querySelector('.errorlist');
    if (group && !errorEl) {
        errorEl = document.createElement('ul');
        errorEl.className = 'errorlist';
        errorEl.setAttribute('role', 'alert');
        errorEl.setAttribute('aria-live', 'polite');
        group.appendChild(errorEl);
    }

    /* ──────────────────────────────────────────────
       6. ВИЗУАЛЬНЫЕ СОСТОЯНИЯ
       ────────────────────────────────────────────── */
    const CSS_VALID = 'is-valid';
    const CSS_ERROR = 'is-invalid';

    function setFieldState(state) {
        input.classList.remove(CSS_VALID, CSS_ERROR);
        if (state) input.classList.add(state);
        input.setAttribute('aria-invalid', state === CSS_ERROR ? 'true' : 'false');
    }

    function showError(msg) {
        if (!errorEl) return;
        errorEl.innerHTML = msg ? '<li>' + msg + '</li>' : '';
    }

    function validateVisual() {
        const len = mask.unmaskedValue.length;
        if (len === 0)                { setFieldState(null);      showError(''); }
        else if (len >= getMinLen())  { setFieldState(CSS_VALID); showError(''); }
        else                          { setFieldState(CSS_ERROR); showError('Введите госномер полностью'); }
    }

    /* ──────────────────────────────────────────────
       7. ТРИГГЕРЫ ВАЛИДАЦИИ
       ────────────────────────────────────────────── */
    function onAccept() {
        const len = mask.unmaskedValue.length;
        if (len >= getMinLen())        { setFieldState(CSS_VALID); showError(''); }
        else if (touched && len > 0)   { setFieldState(null);      showError(''); }
    }

    input.addEventListener('focus', () => {
        clearTimeout(blurTimer);
        mask.updateOptions({ lazy: false });
        showError('');
        if (mask.unmaskedValue.length < getMinLen()) setFieldState(null);
    });

    input.addEventListener('blur', () => {
        touched = true;
        if (mask.unmaskedValue.length === 0) mask.updateOptions({ lazy: true });
        blurTimer = setTimeout(validateVisual, 120);
    });

    /* ──────────────────────────────────────────────
       8. УМНАЯ ВСТАВКА
       ────────────────────────────────────────────── */
    input.addEventListener('paste', (e) => {
        e.preventDefault();
        const text = (e.clipboardData.getData('text') || '').replace(/\s/g, '');
        const prepared = text.split('').map(prepareChar).join('');
        mask.unmaskedValue = prepared;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        validateVisual();
    });

    /* ──────────────────────────────────────────────
       9. ПЕРЕКЛЮЧЕНИЕ ТИПА ТС
       ────────────────────────────────────────────── */
    if (typeSelect) {
        typeSelect.addEventListener('change', () => {
            createMask();
            if (mask.unmaskedValue.length > 0) {
                touched = true;
                validateVisual();
            }
        });
    }

    /* ──────────────────────────────────────────────
       10. ОТПРАВКА: пишем без пробелов
       ────────────────────────────────────────────── */
    form.addEventListener('submit', (e) => {
        const raw = mask.unmaskedValue;

        if (raw.length >= getMinLen()) {
            input.value = raw;
            return;
        }

        if (raw.length === 0) {
            input.value = '';
            return;
        }

        e.preventDefault();
        touched = true;
        validateVisual();
        input.focus();
    });

    /* ──────────────────────────────────────────────
       11. ДОСТУПНОСТЬ
       ────────────────────────────────────────────── */
    input.setAttribute('autocomplete', 'off');
    input.setAttribute('aria-label',   'Государственный регистрационный номер');

    /* ──────────────────────────────────────────────
       12. ИНИЦИАЛИЗАЦИЯ
       ────────────────────────────────────────────── */
    createMask();
    hydrateFromServer();
})();
