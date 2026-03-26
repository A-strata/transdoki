/**
 * phone_mask.js
 *
 * Centralised phone-mask initialisation for Russian mobile numbers.
 *
 * Usage:
 *   1. Add data-phone-mask attribute to <input> elements (via Django widget attrs).
 *   2. Load IMask, then this file (e.g. in {% block extra_js %}).
 *   3. Everything is wired up automatically on DOMContentLoaded.
 *
 * Manual API (if needed after dynamic DOM changes):
 *   PhoneMask.init(inputEl)            — initialise a single input, returns IMask instance
 *   PhoneMask.initAllInForm(formEl)    — initialise all [data-phone-mask] inside a form
 */
(function () {
    'use strict';

    const PHONE_LENGTH  = 10;          // digits after country code
    const MASK_PATTERN  = '+7 (000) 000-00-00';
    const CSS_ERROR     = 'is-invalid';
    const CSS_VALID     = 'is-valid';

    function init(input) {
        if (!input || typeof IMask === 'undefined') return null;

        /* 1. MASK */
        const mask = IMask(input, {
            mask:            MASK_PATTERN,
            lazy:            true,
            placeholderChar: '_',
            overwrite:       'shift',
        });

        input.addEventListener('focus', () => { mask.updateOptions({ lazy: false }); });
        input.addEventListener('blur',  () => {
            if (mask.unmaskedValue.length === 0) mask.updateOptions({ lazy: true });
        });

        /* 2. HYDRATE SERVER VALUE (E.164 → display) */
        const initial = input.value.replace(/\D/g, '');
        if (initial.length === 11 && initial.startsWith('7')) {
            mask.unmaskedValue = initial.slice(1);
        } else if (initial.length === PHONE_LENGTH) {
            mask.unmaskedValue = initial;
        }

        /* 3. SMART PASTE (+7 / 8 / raw 10-digit) */
        input.addEventListener('paste', (e) => {
            e.preventDefault();
            let digits = (e.clipboardData.getData('text') || '').replace(/\D/g, '');
            if      (digits.startsWith('7') && digits.length === 11) digits = digits.slice(1);
            else if (digits.startsWith('8') && digits.length === 11) digits = digits.slice(1);
            else if (digits.startsWith('7') && digits.length === 10) digits = digits.slice(1);
            mask.unmaskedValue = digits.slice(0, PHONE_LENGTH);
            input.dispatchEvent(new Event('input', { bubbles: true }));
            validateVisual();
        });

        /* 4. INLINE ERROR ELEMENT */
        const group = input.parentElement;
        let errorEl = group && group.querySelector('.errorlist');
        if (group && !errorEl) {
            errorEl = document.createElement('ul');
            errorEl.className = 'errorlist';
            errorEl.setAttribute('role', 'alert');
            errorEl.setAttribute('aria-live', 'polite');
            group.appendChild(errorEl);
        }

        /* 5. VISUAL STATES */
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
            if (len === 0)                 { setFieldState(null);      showError(''); }
            else if (len === PHONE_LENGTH) { setFieldState(CSS_VALID); showError(''); }
            else                           { setFieldState(CSS_ERROR); showError('Введите номер полностью'); }
        }

        /* 6. VALIDATION TRIGGERS */
        let blurTimer = null;
        let touched   = false;

        mask.on('accept', () => {
            const len = mask.unmaskedValue.length;
            if (len === PHONE_LENGTH)       { setFieldState(CSS_VALID); showError(''); }
            else if (touched && len > 0)    { setFieldState(null);      showError(''); }
        });

        input.addEventListener('focus', () => {
            clearTimeout(blurTimer);
            showError('');
            if (mask.unmaskedValue.length !== PHONE_LENGTH) setFieldState(null);
        });

        input.addEventListener('blur', () => {
            touched = true;
            blurTimer = setTimeout(validateVisual, 120);
        });

        /* 7. ACCESSIBILITY */
        input.setAttribute('inputmode',    'tel');
        input.setAttribute('autocomplete', 'tel');
        input.setAttribute('aria-label',   'Номер телефона в формате +7');

        return mask;
    }

    function initAllInForm(form) {
        if (!form) return;
        const inputs = Array.from(form.querySelectorAll('[data-phone-mask]'));
        if (!inputs.length) return;

        const masks = inputs.map(init);

        /* 8. FORM SUBMISSION GUARD */
        form.addEventListener('submit', (e) => {
            let firstError = null;
            masks.forEach((mask, i) => {
                if (!mask) return;
                const raw = mask.unmaskedValue;
                if (raw.length === 0) {
                    inputs[i].value = '';                   // optional field — allow empty
                } else if (raw.length === PHONE_LENGTH) {
                    inputs[i].value = '7' + raw;            // E.164 without '+'
                } else if (!firstError) {
                    firstError = { mask, input: inputs[i] };
                }
            });

            if (firstError) {
                e.preventDefault();
                firstError.input.classList.add(CSS_ERROR);
                firstError.input.focus();
            }
        });
    }

    /* AUTO-INIT on DOMContentLoaded */
    document.addEventListener('DOMContentLoaded', () => {
        const forms = new Set();
        document.querySelectorAll('[data-phone-mask]').forEach((input) => {
            const form = input.closest('form');
            if (form) forms.add(form);
        });
        forms.forEach(initAllInForm);
    });

    /* Public API */
    window.PhoneMask = { init: init, initAllInForm: initAllInForm };
})();
