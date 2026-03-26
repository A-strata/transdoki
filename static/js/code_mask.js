(function () {
    const codeInput = document.querySelector('[data-code-mask]');
    if (!codeInput || typeof IMask === 'undefined') return;

    const form = codeInput.closest('form');
    const CODE_LENGTH = 6;

    const mask = IMask(codeInput, {
        mask: '000-000',
        lazy: true,
        placeholderChar: '_',
    });

    // Гидратация: подхватываем то, что пришло с сервера
    if (codeInput.value) {
        mask.value = codeInput.value;
    }

    const group = codeInput.closest('.form-group');
    let errorEl = group && group.querySelector('.errorlist');
    if (group && !errorEl) {
        errorEl = document.createElement('ul');
        errorEl.className = 'errorlist';
        errorEl.setAttribute('role', 'alert');
        errorEl.setAttribute('aria-live', 'polite');
        group.appendChild(errorEl);
    }

    function setFieldState(state) {
        codeInput.classList.remove('is-valid', 'is-invalid');
        if (state) codeInput.classList.add(state);
    }

    function validateVisual() {
        const raw = mask.unmaskedValue;
        if (raw.length === 0) {
            setFieldState(null);
            if (errorEl) errorEl.innerHTML = '';
        } else if (raw.length === CODE_LENGTH) {
            setFieldState('is-valid');
            if (errorEl) errorEl.innerHTML = '';
        } else {
            setFieldState('is-invalid');
            if (errorEl) errorEl.innerHTML = '<li>Введите код подразделения полностью</li>';
        }
    }

    let blurTimer = null;
    let touched   = false;

    mask.on('accept', () => {
        const len = mask.unmaskedValue.length;
        if (len === CODE_LENGTH)     { setFieldState('is-valid');  if (errorEl) errorEl.innerHTML = ''; }
        else if (touched && len > 0) { setFieldState(null);        if (errorEl) errorEl.innerHTML = ''; }
    });

    codeInput.addEventListener('focus', () => {
        clearTimeout(blurTimer);
        if (errorEl) errorEl.innerHTML = '';
        if (mask.unmaskedValue.length !== CODE_LENGTH) setFieldState(null);
        mask.updateOptions({ lazy: false });
    });

    codeInput.addEventListener('blur', () => {
        touched = true;
        if (mask.unmaskedValue.length === 0) mask.updateOptions({ lazy: true });
        blurTimer = setTimeout(validateVisual, 120);
    });

    if (form) {
        form.addEventListener('submit', (e) => {
            const raw = mask.unmaskedValue;

            // Если пусто и не required — ок
            if (raw.length === 0) return;

            // Если не дозаполнено — стоп
            if (raw.length < CODE_LENGTH) {
                e.preventDefault();
                validateVisual();
                codeInput.focus();
            }
            // Если заполнено (raw=6), mask.value уже содержит "123-456" (7 символов)
            // Оно и отправится на сервер в правильном формате.
        });
    }

    // Технические атрибуты
    codeInput.setAttribute('inputmode', 'numeric');
    codeInput.setAttribute('autocomplete', 'off');
})();
