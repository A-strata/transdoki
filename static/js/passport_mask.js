(function () {
    'use strict';

    const input = document.querySelector('[data-passport-mask]');
    const form  = input && input.closest('form');

    if (!input || !form || typeof IMask === 'undefined') return;

    /* ──────────────────────────────────────────────
       1. МАСКА: 00 00 000000  (серия 4 цифры + номер 6 цифр)
       ────────────────────────────────────────────── */
    const TOTAL_DIGITS = 10;

    const mask = IMask(input, {
        mask:            '00 00 000000',
        lazy:            true,
        placeholderChar: '_',
        overwrite:       'shift',
    });

    input.addEventListener('focus', () => { mask.updateOptions({ lazy: false }); });
    input.addEventListener('blur',  () => {
        if (mask.unmaskedValue.length === 0) mask.updateOptions({ lazy: true });
    });

    /* ──────────────────────────────────────────────
       2. ГИДРАТАЦИЯ: сервер отдаёт «1234567890» или «12 34 567890»
       ────────────────────────────────────────────── */
    const initial = input.value.replace(/\D/g, '');
    if (initial.length === TOTAL_DIGITS) {
        mask.unmaskedValue = initial;
    }

    /* ──────────────────────────────────────────────
       3. УМНАЯ ВСТАВКА
       ────────────────────────────────────────────── */
    input.addEventListener('paste', (e) => {
        e.preventDefault();
        const digits = (e.clipboardData.getData('text') || '').replace(/\D/g, '');
        mask.unmaskedValue = digits.slice(0, TOTAL_DIGITS);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        validateVisual();
    });

    /* ──────────────────────────────────────────────
       4. ЭЛЕМЕНТ ОШИБКИ
       ────────────────────────────────────────────── */
    const group = input.closest('.form-group');
    let errorEl = group && group.querySelector('.errorlist');
    if (group && !errorEl) {
        errorEl = document.createElement('ul');
        errorEl.className = 'errorlist';
        errorEl.setAttribute('role', 'alert');
        errorEl.setAttribute('aria-live', 'polite');
        group.appendChild(errorEl);
    }

    /* ──────────────────────────────────────────────
       5. ВИЗУАЛЬНЫЕ СОСТОЯНИЯ
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
        if (len === 0)               { setFieldState(null);      showError(''); }
        else if (len === TOTAL_DIGITS) { setFieldState(CSS_VALID); showError(''); }
        else                         { setFieldState(CSS_ERROR); showError('Введите серию и номер паспорта полностью'); }
    }

    /* ──────────────────────────────────────────────
       6. ТРИГГЕРЫ ВАЛИДАЦИИ
       ────────────────────────────────────────────── */
    let blurTimer = null;
    let touched   = false;

    mask.on('accept', () => {
        const len = mask.unmaskedValue.length;
        if (len === TOTAL_DIGITS)       { setFieldState(CSS_VALID); showError(''); }
        else if (touched && len > 0)    { setFieldState(null);      showError(''); }
    });

    input.addEventListener('focus', () => {
        clearTimeout(blurTimer);
        showError('');
        if (mask.unmaskedValue.length !== TOTAL_DIGITS) setFieldState(null);
    });

    input.addEventListener('blur', () => {
        touched = true;
        blurTimer = setTimeout(validateVisual, 120);
    });

    /* ──────────────────────────────────────────────
       7. ОТПРАВКА: пишем 10 чистых цифр
       ────────────────────────────────────────────── */
    form.addEventListener('submit', (e) => {
        const raw = mask.unmaskedValue;

        if (raw.length === TOTAL_DIGITS) {
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
       8. ДОСТУПНОСТЬ
       ────────────────────────────────────────────── */
    input.setAttribute('inputmode',    'numeric');
    input.setAttribute('autocomplete', 'off');
    input.setAttribute('aria-label',   'Серия и номер паспорта в формате XX XX XXXXXX');
})();
