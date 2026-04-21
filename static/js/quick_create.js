(function () {
    'use strict';

    var config = document.getElementById('qc-config');
    if (!config) return;

    var orgCreateUrl = config.dataset.orgCreateUrl;
    var personCreateUrl = config.dataset.personCreateUrl;
    var vehicleCreateUrl = config.dataset.vehicleCreateUrl;
    var orgSuggestionsUrl = config.dataset.orgSuggestionsUrl;

    var orgModal = document.getElementById('qc-org-modal');
    var personModal = document.getElementById('qc-person-modal');
    var vehicleModal = document.getElementById('qc-vehicle-modal');

    var orgForm = orgModal ? orgModal.querySelector('form') : null;
    var personForm = personModal ? personModal.querySelector('form') : null;
    var vehicleForm = vehicleModal ? vehicleModal.querySelector('form') : null;

    var currentTarget = null;

    // ── CSRF ────────────────────────────────────────────────────────────────
    function getCsrfToken() {
        for (var i = 0; i < document.cookie.split(';').length; i++) {
            var parts = document.cookie.split(';')[i].trim().split('=');
            if (parts[0] === 'csrftoken') return decodeURIComponent(parts[1]);
        }
        return '';
    }

    // ── Error helpers ───────────────────────────────────────────────────────
    function clearErrors(form) {
        form.querySelectorAll('.modal-field-error').forEach(function (el) {
            el.textContent = '';
        });
        form.querySelectorAll('.is-invalid').forEach(function (el) {
            el.classList.remove('is-invalid');
        });
        var box = form.querySelector('.modal-form-errors');
        if (box) box.hidden = true;
    }

    function showFieldError(form, name, msg) {
        var errEl = form.querySelector('[data-err="' + name + '"]');
        if (errEl) errEl.textContent = msg;
        var input = form.querySelector('[name="' + name + '"]');
        if (input) input.classList.add('is-invalid');
    }

    function showGeneralError(form, msg) {
        var box = form.querySelector('.modal-form-errors');
        if (box) {
            box.textContent = msg;
            box.hidden = false;
        }
    }

    // ── Phone normalization ─────────────────────────────────────────────────
    // Переводим все [data-phone-mask]-поля в E.164 ('79991234567') ДО чтения
    // значений в payload. Делаем явно тут, чтобы не зависеть от порядка
    // подключения/регистрации submit-хендлеров phone_mask.js и quick_create.js.
    // Серверная нормализация (PersonQuickForm.clean_phone) это продублирует,
    // но на фронте мы хотим единообразное представление в payload.
    function normalizePhoneFields(form) {
        form.querySelectorAll('[data-phone-mask]').forEach(function (el) {
            var mask = el._phoneMask;
            if (!mask) return;
            var raw = mask.unmaskedValue;
            if (raw.length === 10) {
                el.value = '7' + raw;
            } else if (raw.length === 0) {
                el.value = '';
            }
            // иначе оставляем как есть — сервер вернёт осмысленную ошибку
        });
    }

    // ── Submit ──────────────────────────────────────────────────────────────
    function submitForm(form, url, modal) {
        clearErrors(form);
        normalizePhoneFields(form);

        var submitBtn = form.querySelector('button[type="submit"]');
        var originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Сохраняем\u2026';

        var params = new URLSearchParams();
        form.querySelectorAll('input[name], select[name]').forEach(function (el) {
            if (el.type !== 'hidden' || el.name === 'ogrn' || el.name === 'kpp' || el.name === 'address') {
                params.set(el.name, el.value.trim());
            }
        });
        // Hidden fields that are actual form data (not csrf)
        form.querySelectorAll('input[type="hidden"]').forEach(function (el) {
            if (el.name !== 'csrfmiddlewaretoken') {
                params.set(el.name, el.value.trim());
            }
        });

        fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: params.toString(),
        })
            .then(function (resp) {
                return resp.json().then(function (body) {
                    return { ok: resp.ok, body: body };
                });
            })
            .then(function (result) {
                if (result.ok) {
                    if (currentTarget) {
                        var option = new Option(result.body.text, result.body.id, true, true);
                        currentTarget.add(option);
                    }
                    modal.hidden = true;
                    return;
                }

                var errors = result.body.errors || {};
                var hasFieldError = false;
                for (var field in errors) {
                    var errEl = form.querySelector('[data-err="' + field + '"]');
                    if (errEl) {
                        showFieldError(form, field, errors[field]);
                        hasFieldError = true;
                    }
                }
                if (!hasFieldError) {
                    var msgs = [];
                    for (var k in errors) msgs.push(errors[k]);
                    showGeneralError(form, msgs.join('; ') || 'Ошибка сохранения');
                }

                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            })
            .catch(function () {
                showGeneralError(form, 'Ошибка соединения, попробуйте снова.');
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            });
    }

    // ── Reset on modal close ────────────────────────────────────────────────
    function observeClose(modal) {
        if (!modal) return;
        new MutationObserver(function (mutations) {
            mutations.forEach(function (m) {
                if (m.attributeName === 'hidden' && modal.hidden) {
                    var form = modal.querySelector('form');
                    if (form) {
                        form.reset();
                        clearErrors(form);
                        // Reset submit button
                        var btn = form.querySelector('button[type="submit"]');
                        if (btn) {
                            btn.disabled = false;
                        }
                    }
                    // Reset autocomplete inputs (initAutocomplete replaces select with text input)
                    modal.querySelectorAll('.autocomplete-input').forEach(function (el) {
                        el.value = '';
                    });
                    currentTarget = null;
                }
            });
        }).observe(modal, { attributes: true, attributeFilter: ['hidden'] });
    }

    observeClose(orgModal);
    observeClose(personModal);
    observeClose(vehicleModal);

    // ── Organization: fill by INN ───────────────────────────────────────────
    var innFillBtn = document.getElementById('qc-org-inn-fill');
    if (innFillBtn && orgForm) {
        innFillBtn.addEventListener('click', function () {
            var innInput = orgForm.querySelector('[name="inn"]');
            var inn = innInput ? innInput.value.trim() : '';
            if (!inn) return;

            clearErrors(orgForm);
            innFillBtn.disabled = true;
            innFillBtn.textContent = '\u2026';

            fetch(orgSuggestionsUrl + '?inn=' + encodeURIComponent(inn))
                .then(function (resp) { return resp.json(); })
                .then(function (data) {
                    if (data.error) {
                        showFieldError(orgForm, 'inn', data.error);
                        return;
                    }
                    var fields = { full_name: data.full_name, short_name: data.short_name,
                                   ogrn: data.ogrn, kpp: data.kpp, address: data.address };
                    for (var name in fields) {
                        var el = orgForm.querySelector('[name="' + name + '"]');
                        if (el && fields[name]) el.value = fields[name];
                    }
                })
                .catch(function () { /* пользователь заполнит вручную */ })
                .finally(function () {
                    innFillBtn.disabled = false;
                    innFillBtn.textContent = 'Заполнить по ИНН';
                });
        });
    }

    // ── Vehicle: filter types on open ───────────────────────────────────────
    var vehicleTypeSelect = vehicleModal ? vehicleModal.querySelector('[name="vehicle_type"]') : null;
    var allVehicleOptions = vehicleTypeSelect ? [].slice.call(vehicleTypeSelect.options) : [];

    function filterVehicleTypes(allowedTypes) {
        if (!vehicleTypeSelect) return;
        allVehicleOptions.forEach(function (opt) {
            opt.hidden = allowedTypes.length > 0 && allowedTypes.indexOf(opt.value) === -1;
        });
        var firstVisible = allVehicleOptions.filter(function (o) { return !o.hidden; })[0];
        if (firstVisible) vehicleTypeSelect.value = firstVisible.value;
        // Программная смена .value не вызывает change — нужно вручную,
        // чтобы маска госномера переключилась на нужный формат
        vehicleTypeSelect.dispatchEvent(new Event('change'));
    }

    // ── Button click delegation ─────────────────────────────────────────────
    document.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-qc-type]');
        if (!btn) return;

        var type = btn.dataset.qcType;
        var targetId = btn.dataset.qcTarget;
        currentTarget = document.getElementById(targetId);

        if (type === 'organization' && orgModal && orgForm) {
            orgForm.reset();
            clearErrors(orgForm);
            orgModal.hidden = false;
            var innInput = orgForm.querySelector('[name="inn"]');
            if (innInput) innInput.focus();
        } else if (type === 'person' && personModal && personForm) {
            personForm.reset();
            clearErrors(personForm);
            // Предзаполнить компанию-владельца из перевозчика основной формы
            var employerSelect = document.getElementById('qc-person-employer');
            var carrierSelect = document.getElementById('id_carrier');
            if (employerSelect && carrierSelect && carrierSelect.value) {
                var opt = carrierSelect.options[carrierSelect.selectedIndex];
                var carrierText = (opt && opt.value) ? opt.text : '';
                if (carrierText) {
                    var opt = new Option(carrierText, carrierSelect.value, true, true);
                    employerSelect.innerHTML = '';
                    employerSelect.add(opt);
                    var empInput = employerSelect.parentNode.querySelector('.autocomplete-input');
                    if (empInput) empInput.value = carrierText;
                }
            } else if (employerSelect) {
                employerSelect.value = '';
                var empInput = employerSelect.parentNode.querySelector('.autocomplete-input');
                if (empInput) empInput.value = '';
            }
            personModal.hidden = false;
            var surnameInput = personForm.querySelector('[name="surname"]');
            if (surnameInput) surnameInput.focus();
        } else if (type === 'vehicle' && vehicleModal && vehicleForm) {
            var types = (btn.dataset.qcVehicleTypes || '').split(',').filter(Boolean);
            filterVehicleTypes(types);
            vehicleForm.reset();
            clearErrors(vehicleForm);
            // Re-apply filter after reset (reset may restore default selection)
            filterVehicleTypes(types);
            // Предзаполнить владельца из перевозчика основной формы
            var ownerSelect = document.getElementById('qc-vehicle-owner');
            var carrierSelect = document.getElementById('id_carrier');
            if (ownerSelect && carrierSelect && carrierSelect.value) {
                var opt = carrierSelect.options[carrierSelect.selectedIndex];
                var carrierText = (opt && opt.value) ? opt.text : '';
                if (carrierText) {
                    var newOpt = new Option(carrierText, carrierSelect.value, true, true);
                    ownerSelect.innerHTML = '';
                    ownerSelect.add(newOpt);
                    var ownerInput = ownerSelect.parentNode.querySelector('.autocomplete-input');
                    if (ownerInput) ownerInput.value = carrierText;
                }
            } else if (ownerSelect) {
                ownerSelect.value = '';
                var ownerInput = ownerSelect.parentNode.querySelector('.autocomplete-input');
                if (ownerInput) ownerInput.value = '';
            }
            vehicleModal.hidden = false;
            var grnInput = vehicleForm.querySelector('[name="grn"]');
            if (grnInput) {
                if (typeof initGrnMask === 'function') initGrnMask(grnInput);
                grnInput.focus();
            }
        }
    });

    // ── Form submit handlers ────────────────────────────────────────────────
    if (orgForm) {
        orgForm.addEventListener('submit', function (e) {
            e.preventDefault();
            submitForm(orgForm, orgCreateUrl, orgModal);
        });
    }

    if (personForm) {
        personForm.addEventListener('submit', function (e) {
            e.preventDefault();
            submitForm(personForm, personCreateUrl, personModal);
        });
    }

    if (vehicleForm) {
        vehicleForm.addEventListener('submit', function (e) {
            e.preventDefault();
            submitForm(vehicleForm, vehicleCreateUrl, vehicleModal);
        });
    }

    // ── Init autocomplete for selects inside modals ───────────────────────
    if (typeof initAutocomplete === 'function') {
        initAutocomplete('qc-person-employer');
        initAutocomplete('qc-vehicle-owner');
    }
})();
