(function () {
    'use strict';

    function getCsrfToken() {
        for (const cookie of document.cookie.split(';')) {
            const [k, v] = cookie.trim().split('=');
            if (k === 'csrftoken') return decodeURIComponent(v);
        }
        return '';
    }

    // ── Modal DOM (built once) ──────────────────────────────────────────────
    let overlay, modal, modalTitle, fieldsContainer, errorBox, submitBtn;

    function buildModal() {
        overlay = document.createElement('div');
        overlay.style.cssText = [
            'display:none; position:fixed; inset:0; z-index:1000;',
            'background:rgba(0,0,0,.45); align-items:center; justify-content:center;',
        ].join('');

        modal = document.createElement('div');
        modal.style.cssText = [
            'background:#fff; border-radius:14px; padding:20px 24px;',
            'width:100%; max-width:460px; box-shadow:0 16px 40px rgba(15,23,42,.18);',
            'box-sizing:border-box; margin:16px;',
        ].join('');

        modalTitle = document.createElement('h3');
        modalTitle.style.cssText = 'margin:0 0 14px; font-size:1.05rem; font-weight:700; color:#111827;';

        errorBox = document.createElement('div');
        errorBox.style.cssText = [
            'display:none; margin-bottom:10px; padding:8px 10px;',
            'background:#fef2f2; border:1px solid #fecaca; border-radius:8px;',
            'font-size:.88rem; color:#991b1b;',
        ].join('');

        fieldsContainer = document.createElement('div');

        const actions = document.createElement('div');
        actions.style.cssText = 'display:flex; gap:8px; margin-top:16px; justify-content:flex-end;';

        const cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.textContent = 'Отмена';
        cancelBtn.style.cssText = 'padding:8px 14px; border-radius:8px; border:1px solid #e5e7eb; background:#fff; cursor:pointer; font-size:.9rem;';
        cancelBtn.addEventListener('click', closeModal);

        submitBtn = document.createElement('button');
        submitBtn.type = 'button';
        submitBtn.textContent = 'Создать';
        submitBtn.style.cssText = 'padding:8px 14px; border-radius:8px; border:1px solid #2563eb; background:#2563eb; color:#fff; cursor:pointer; font-size:.9rem; font-weight:600;';

        actions.append(cancelBtn, submitBtn);
        modal.append(modalTitle, errorBox, fieldsContainer, actions);
        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) closeModal();
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && overlay.style.display === 'flex') closeModal();
        });
    }

    function closeModal() {
        overlay.style.display = 'none';
        fieldsContainer.innerHTML = '';
        errorBox.style.display = 'none';
        currentTarget = null;
    }

    // ── Field helpers ───────────────────────────────────────────────────────
    function makeTextInput(name, label, required) {
        const wrap = document.createElement('div');
        wrap.style.cssText = 'margin-bottom:10px;';

        const lbl = document.createElement('label');
        lbl.style.cssText = 'display:block; margin-bottom:4px; font-size:.88rem; font-weight:600; color:#374151;';
        lbl.textContent = label + (required ? ' *' : '');

        const input = document.createElement('input');
        input.type = 'text';
        input.name = name;
        input.style.cssText = 'width:100%; border:1px solid #e5e7eb; border-radius:8px; padding:8px 10px; font-size:.92rem; box-sizing:border-box;';

        const err = document.createElement('span');
        err.dataset.errField = name;
        err.style.cssText = 'display:none; font-size:.82rem; color:#991b1b; margin-top:3px; display:none;';

        wrap.append(lbl, input, err);
        return wrap;
    }

    function getInput(name) {
        return fieldsContainer.querySelector(`input[name="${name}"], select[name="${name}"]`);
    }

    function clearErrors() {
        fieldsContainer.querySelectorAll('[data-err-field]').forEach(el => {
            el.style.display = 'none';
            el.textContent = '';
        });
        fieldsContainer.querySelectorAll('input, select').forEach(el => {
            el.style.borderColor = '#e5e7eb';
        });
        errorBox.style.display = 'none';
    }

    function showFieldError(name, msg) {
        const err = fieldsContainer.querySelector(`[data-err-field="${name}"]`);
        if (err) {
            err.textContent = msg;
            err.style.display = 'block';
        }
        const input = getInput(name);
        if (input) input.style.borderColor = '#ef4444';
    }

    // ── Submit helper ───────────────────────────────────────────────────────
    let currentTarget = null;
    let currentEndpoint = null;
    let currentFields = null;

    async function submitModal() {
        clearErrors();

        const params = new URLSearchParams();
        for (const name of currentFields) {
            const input = getInput(name);
            if (input) params.set(name, input.value.trim());
        }

        submitBtn.disabled = true;
        submitBtn.textContent = 'Сохраняем…';

        try {
            const resp = await fetch(currentEndpoint, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: params.toString(),
            });

            const data = await resp.json();

            if (!resp.ok) {
                const errors = data.errors || {};
                let hasFieldError = false;
                for (const [field, msg] of Object.entries(errors)) {
                    if (currentFields.includes(field)) {
                        showFieldError(field, msg);
                        hasFieldError = true;
                    }
                }
                if (!hasFieldError) {
                    errorBox.textContent = Object.values(errors).join('; ') || 'Ошибка сохранения';
                    errorBox.style.display = 'block';
                }
            } else {
                const option = new Option(data.text, data.id, true, true);
                currentTarget.add(option);
                closeModal();
            }
        } catch (_) {
            errorBox.textContent = 'Ошибка соединения, попробуйте снова.';
            errorBox.style.display = 'block';
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Создать';
        }
    }

    // ── Organization modal ──────────────────────────────────────────────────
    function openOrgModal(targetSelectId) {
        currentTarget = document.getElementById(targetSelectId);
        if (!currentTarget) return;

        currentEndpoint = '/organizations/quick-create/';
        currentFields = ['inn', 'full_name', 'short_name', 'ogrn', 'kpp', 'address'];

        modalTitle.textContent = 'Добавить организацию';

        // INN row with "Заполнить по ИНН" button
        const innWrap = document.createElement('div');
        innWrap.style.cssText = 'margin-bottom:10px;';

        const innLbl = document.createElement('label');
        innLbl.style.cssText = 'display:block; margin-bottom:4px; font-size:.88rem; font-weight:600; color:#374151;';
        innLbl.textContent = 'ИНН *';

        const innRow = document.createElement('div');
        innRow.style.cssText = 'display:flex; gap:6px;';

        const innInput = document.createElement('input');
        innInput.type = 'text';
        innInput.name = 'inn';
        innInput.style.cssText = 'flex:1; border:1px solid #e5e7eb; border-radius:8px; padding:8px 10px; font-size:.92rem; box-sizing:border-box;';

        const fillBtn = document.createElement('button');
        fillBtn.type = 'button';
        fillBtn.textContent = 'Заполнить по ИНН';
        fillBtn.style.cssText = 'white-space:nowrap; padding:8px 10px; border-radius:8px; border:1px solid #d1d5db; background:#f9fafb; font-size:.84rem; cursor:pointer;';

        const innErr = document.createElement('span');
        innErr.dataset.errField = 'inn';
        innErr.style.cssText = 'display:none; font-size:.82rem; color:#991b1b; margin-top:3px;';

        innRow.append(innInput, fillBtn);
        innWrap.append(innLbl, innRow, innErr);
        fieldsContainer.appendChild(innWrap);
        fieldsContainer.appendChild(makeTextInput('full_name', 'Полное наименование', true));
        fieldsContainer.appendChild(makeTextInput('short_name', 'Краткое наименование', true));

        // Hidden fields for extra DaData data
        ['ogrn', 'kpp', 'address'].forEach(function (name) {
            const hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = name;
            fieldsContainer.appendChild(hidden);
        });

        fillBtn.addEventListener('click', async function () {
            const inn = innInput.value.trim();
            if (!inn) return;
            clearErrors();
            fillBtn.disabled = true;
            fillBtn.textContent = '…';
            try {
                const url = (window.QC_ORG_SUGGESTIONS_URL || '/organizations/api/suggestions_by_inn/')
                    + '?inn=' + encodeURIComponent(inn);
                const resp = await fetch(url);
                const data = await resp.json();
                if (data.full_name) getInput('full_name').value = data.full_name;
                if (data.short_name) getInput('short_name').value = data.short_name;
                ['ogrn', 'kpp', 'address'].forEach(function (name) {
                    if (data[name]) getInput(name).value = data[name];
                });
            } catch (_) {
                // silently ignore — user can fill manually
            } finally {
                fillBtn.disabled = false;
                fillBtn.textContent = 'Заполнить по ИНН';
            }
        });

        submitBtn.onclick = submitModal;
        overlay.style.display = 'flex';
        innInput.focus();
    }

    // ── Person modal ────────────────────────────────────────────────────────
    function openPersonModal(targetSelectId) {
        currentTarget = document.getElementById(targetSelectId);
        if (!currentTarget) return;

        currentEndpoint = '/persons/quick-create/';
        currentFields = ['surname', 'name', 'patronymic', 'phone'];

        modalTitle.textContent = 'Добавить водителя';

        fieldsContainer.appendChild(makeTextInput('surname', 'Фамилия', true));
        fieldsContainer.appendChild(makeTextInput('name', 'Имя', true));
        fieldsContainer.appendChild(makeTextInput('patronymic', 'Отчество', false));
        fieldsContainer.appendChild(makeTextInput('phone', 'Телефон', false));

        submitBtn.onclick = submitModal;
        overlay.style.display = 'flex';
        getInput('surname').focus();
    }

    // ── Vehicle modal ───────────────────────────────────────────────────────
    const VEHICLE_TYPE_LABELS = {
        single: 'Грузовик одиночный',
        truck: 'Тягач седельный',
        trailer: 'Прицеп',
    };

    const PROPERTY_TYPE_OPTIONS = [
        ['property',   'Собственность'],
        ['coproperty', 'Совместная собственность супругов'],
        ['rent',       'Аренда'],
        ['leasing',    'Лизинг'],
        ['unpaid',     'Безвозмездное пользование'],
    ];

    function makeSelectField(name, label, options, required) {
        const wrap = document.createElement('div');
        wrap.style.cssText = 'margin-bottom:10px;';
        const lbl = document.createElement('label');
        lbl.style.cssText = 'display:block; margin-bottom:4px; font-size:.88rem; font-weight:600; color:#374151;';
        lbl.textContent = label + (required ? ' *' : '');
        const sel = document.createElement('select');
        sel.name = name;
        sel.style.cssText = 'width:100%; border:1px solid #e5e7eb; border-radius:8px; padding:8px 10px; font-size:.92rem; box-sizing:border-box;';
        options.forEach(function ([val, text]) {
            sel.add(new Option(text, val));
        });
        const err = document.createElement('span');
        err.dataset.errField = name;
        err.style.cssText = 'display:none; font-size:.82rem; color:#991b1b; margin-top:3px;';
        wrap.append(lbl, sel, err);
        return wrap;
    }

    function openVehicleModal(targetSelectId, allowedTypes) {
        currentTarget = document.getElementById(targetSelectId);
        if (!currentTarget) return;

        const orgs = window.QC_ORGS || [];

        currentEndpoint = '/vehicles/quick-create/';
        currentFields = ['vehicle_type', 'grn', 'brand', 'model', 'property_type', 'owner_id'];

        modalTitle.textContent = 'Добавить транспортное средство';

        // vehicle_type
        const typeOptions = allowedTypes.map(function (t) {
            return [t, VEHICLE_TYPE_LABELS[t] || t];
        });
        fieldsContainer.appendChild(makeSelectField('vehicle_type', 'Тип ТС', typeOptions, true));

        fieldsContainer.appendChild(makeTextInput('grn', 'Рег. номер', true));
        fieldsContainer.appendChild(makeTextInput('brand', 'Марка', true));
        fieldsContainer.appendChild(makeTextInput('model', 'Модель', false));
        fieldsContainer.appendChild(makeSelectField('property_type', 'Тип владения', PROPERTY_TYPE_OPTIONS, true));

        // owner — с поиском через initAutocomplete
        const ownerWrap = document.createElement('div');
        ownerWrap.style.cssText = 'margin-bottom:10px;';
        const ownerLbl = document.createElement('label');
        ownerLbl.style.cssText = 'display:block; margin-bottom:4px; font-size:.88rem; font-weight:600; color:#374151;';
        ownerLbl.textContent = 'Владелец *';
        const ownerSelect = document.createElement('select');
        ownerSelect.id = 'qc-vehicle-owner';
        ownerSelect.name = 'owner_id';
        ownerSelect.style.cssText = 'width:100%; border:1px solid #e5e7eb; border-radius:8px; padding:8px 10px; font-size:.92rem; box-sizing:border-box;';
        ownerSelect.add(new Option('— начните вводить —', ''));
        orgs.forEach(function (c) {
            ownerSelect.add(new Option(c.short_name, c.id));
        });
        const ownerErr = document.createElement('span');
        ownerErr.dataset.errField = 'owner_id';
        ownerErr.style.cssText = 'display:none; font-size:.82rem; color:#991b1b; margin-top:3px;';
        ownerWrap.append(ownerLbl, ownerSelect, ownerErr);
        fieldsContainer.appendChild(ownerWrap);
        setTimeout(function () {
            if (typeof initAutocomplete === 'function') {
                initAutocomplete('qc-vehicle-owner');
                const acInput = ownerWrap.querySelector('.autocomplete-input');
                if (acInput) {
                    acInput.style.cssText = 'width:100%; border:1px solid #e5e7eb; border-radius:8px; padding:8px 10px; font-size:.92rem; box-sizing:border-box;';
                }
            }
        }, 0);

        submitBtn.onclick = submitModal;
        overlay.style.display = 'flex';
        getInput('grn').focus();
    }

    // ── Init ────────────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', function () {
        buildModal();

        document.querySelectorAll('[data-qc-type="organization"]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                openOrgModal(btn.dataset.qcTarget);
            });
        });

        document.querySelectorAll('[data-qc-type="person"]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                openPersonModal(btn.dataset.qcTarget);
            });
        });

        document.querySelectorAll('[data-qc-type="vehicle"]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const types = (btn.dataset.qcVehicleTypes || '').split(',').filter(Boolean);
                openVehicleModal(btn.dataset.qcTarget, types);
            });
        });
    });
})();
