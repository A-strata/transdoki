/**
 * Маска госномера ТС (IMask).
 * Экспортирует window.initGrnMask(input) для инициализации на конкретном элементе.
 * При загрузке автоматически инициализирует все [data-grn-mask] на странице.
 */
(function () {
    'use strict';

    var LAT_TO_CYR = {
        'A': 'А', 'B': 'В', 'E': 'Е', 'K': 'К', 'M': 'М',
        'H': 'Н', 'O': 'О', 'P': 'Р', 'C': 'С', 'T': 'Т',
        'Y': 'У', 'X': 'Х',
    };

    function prepareChar(ch) {
        ch = ch.toUpperCase();
        return LAT_TO_CYR[ch] || ch;
    }

    var CYR_REGEX = /[АВЕКМНОРСТУХ]/;

    var TRUCK_OPTS = {
        mask:            'L 000 LL 00[0]',
        definitions:     { 'L': CYR_REGEX },
        prepareChar:     prepareChar,
        lazy:            true,
        placeholderChar: '_',
        overwrite:       'shift',
    };

    var TRAILER_OPTS = {
        mask:            'LL 0000 00[0]',
        definitions:     { 'L': CYR_REGEX },
        prepareChar:     prepareChar,
        lazy:            true,
        placeholderChar: '_',
        overwrite:       'shift',
    };

    function initGrnMask(input) {
        if (!input || typeof IMask === 'undefined') return;
        if (input._grnMaskInitialized) return;
        input._grnMaskInitialized = true;

        var form = input.closest('form');
        var typeSelect = form ? form.querySelector('[name="vehicle_type"]') : null;

        var mask = null;
        var touched = false;
        var blurTimer = null;

        function getOpts() {
            if (typeSelect && typeSelect.value === 'trailer') return TRAILER_OPTS;
            return TRUCK_OPTS;
        }

        function getMinLen() {
            return (typeSelect && typeSelect.value === 'trailer') ? 7 : 8;
        }

        function createMask() {
            var raw = mask ? mask.unmaskedValue : input.value.replace(/\s/g, '');
            if (mask) mask.destroy();
            mask = IMask(input, getOpts());
            mask.on('accept', onAccept);
            if (raw) mask.unmaskedValue = raw;
        }

        function hydrateFromServer() {
            var raw = input.value.replace(/\s/g, '');
            if (raw) mask.unmaskedValue = raw;
        }

        var group = input.closest('.field') || input.closest('.modal-field');
        var errorEl = group ? group.querySelector('.errorlist') : null;
        if (group && !errorEl) {
            errorEl = document.createElement('ul');
            errorEl.className = 'errorlist';
            errorEl.setAttribute('role', 'alert');
            errorEl.setAttribute('aria-live', 'polite');
            group.appendChild(errorEl);
        }

        var CSS_VALID = 'is-valid';
        var CSS_ERROR = 'is-invalid';

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
            var len = mask.unmaskedValue.length;
            if (len === 0)               { setFieldState(null);      showError(''); }
            else if (len >= getMinLen())  { setFieldState(CSS_VALID); showError(''); }
            else                         { setFieldState(CSS_ERROR); showError('Введите госномер полностью'); }
        }

        function onAccept() {
            var len = mask.unmaskedValue.length;
            if (len >= getMinLen())        { setFieldState(CSS_VALID); showError(''); }
            else if (touched && len > 0)   { setFieldState(null);      showError(''); }
        }

        input.addEventListener('focus', function () {
            clearTimeout(blurTimer);
            mask.updateOptions({ lazy: false });
            showError('');
            if (mask.unmaskedValue.length < getMinLen()) setFieldState(null);
        });

        input.addEventListener('blur', function () {
            touched = true;
            if (mask.unmaskedValue.length === 0) mask.updateOptions({ lazy: true });
            blurTimer = setTimeout(validateVisual, 120);
        });

        input.addEventListener('paste', function (e) {
            e.preventDefault();
            var text = (e.clipboardData.getData('text') || '').replace(/\s/g, '');
            var prepared = text.split('').map(prepareChar).join('');
            mask.unmaskedValue = prepared;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            validateVisual();
        });

        if (typeSelect) {
            typeSelect.addEventListener('change', function () {
                createMask();
                if (mask.unmaskedValue.length > 0) {
                    touched = true;
                    validateVisual();
                }
            });
        }

        if (form) {
            form.addEventListener('submit', function (e) {
                var raw = mask.unmaskedValue;
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
        }

        input.setAttribute('autocomplete', 'off');
        input.setAttribute('aria-label', 'Государственный регистрационный номер');

        createMask();
        hydrateFromServer();
    }

    window.initGrnMask = initGrnMask;

    document.querySelectorAll('[data-grn-mask]').forEach(function (el) {
        initGrnMask(el);
    });
})();
