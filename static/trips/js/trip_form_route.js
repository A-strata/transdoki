/**
 * Route Builder — мультиточечный маршрут в форме рейса.
 *
 * Читает начальные данные из #route-config[data-points].
 * На сабмит пишет JSON в hidden input[name=points_json].
 */
(function () {
    'use strict';

    var config = document.getElementById('route-config');
    if (!config) return;

    var container = document.getElementById('route-builder');
    var hiddenInput = document.getElementById('route-points-json');
    var orgSearchUrl = config.dataset.orgSearchUrl || '';
    var addressSuggestUrl = config.dataset.addressSuggestUrl || '';

    var LOAD_LABELS = { rear: 'Задняя', top: 'Верхняя', side: 'Боковая' };
    var TYPE_CFG = {
        LOAD: { label: 'Погрузка', orgLabel: 'Отправитель' },
        UNLOAD: { label: 'Выгрузка', orgLabel: 'Получатель' },
    };

    var nextId = Date.now();
    var points = [];

    // ── Инициализация ──
    try {
        points = JSON.parse(config.dataset.points || '[]');
    } catch (e) {
        points = [];
    }
    // Присваиваем _uid для трекинга; точки с ошибками — развёрнуты
    points.forEach(function (pt) {
        pt._uid = nextId++;
        if (pt.errors) pt.expanded = true;
        else if (pt.expanded === undefined) pt.expanded = false;
    });

    // ── Утилиты ──
    function emptyPoint(type) {
        return {
            _uid: nextId++,
            point_type: type,
            address: '',
            planned_date: '',
            organization: '',
            organization_name: '',
            loading_type: '',
            contact_name: '',
            contact_phone: '',
            expanded: true,
            _justExpanded: true,
            errors: null,
        };
    }

    function formatDateChip(isoStr) {
        if (!isoStr) return '';
        var d = new Date(isoStr);
        if (isNaN(d.getTime())) return '';
        return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
    }

    // ── SVG иконки (Lucide, 16×16, viewBox 0 0 24 24, stroke-width 1.2) ──
    var SVG_UP   = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"><path d="m18 15-6-6-6 6"/></svg>';
    var SVG_DOWN = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>';
    var SVG_DEL  = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1.1-.9 2-2 2H7c-1.1 0-2-.9-2-2V6"/><path d="M8 6V4c0-1.1.9-2 2-2h4c1.1 0 2 .9 2 2v2"/></svg>';
    var SVG_CHEV = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>';
    var SVG_PLUS = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>';

    // ── Рендеринг ──
    function render() {
        // Сохраняем фокус
        var activeId = document.activeElement ? document.activeElement.id : null;

        container.innerHTML = '';

        points.forEach(function (pt, idx) {
            var el = renderPoint(pt, idx);
            if (idx < points.length - 1) el.classList.add('rp--has-next');
            container.appendChild(el);
        });

        // Кнопки добавления
        var addRow = document.createElement('div');
        addRow.className = 'route-add-row';
        addRow.innerHTML =
            '<button type="button" class="tms-btn tms-btn-light tms-btn-sm rp-add-load" data-add="LOAD">' + SVG_PLUS + ' Погрузка</button>' +
            '<button type="button" class="tms-btn tms-btn-light tms-btn-sm rp-add-unload" data-add="UNLOAD">' + SVG_PLUS + ' Выгрузка</button>';
        container.appendChild(addRow);

        addRow.querySelectorAll('[data-add]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                points.push(emptyPoint(btn.dataset.add));
                render();
                scrollToLast();
            });
        });

        // Синхронизация hidden input
        syncHidden();

        // Восстановление фокуса
        if (activeId) {
            var el = document.getElementById(activeId);
            if (el) el.focus();
        }
    }

    function renderPoint(pt, idx) {
        var typeClass = pt.point_type === 'LOAD' ? 'rp--load' : 'rp--unload';
        var cfg = TYPE_CFG[pt.point_type] || TYPE_CFG.LOAD;

        var div = document.createElement('div');
        div.className = 'rp ' + typeClass;

        // Кружок
        var dot = document.createElement('div');
        dot.className = 'rp-dot';
        div.appendChild(dot);

        // Карточка
        var card = document.createElement('div');
        card.className = 'rp-card' + (pt.expanded ? ' is-expanded' : '');

        // Свёрнутая строка
        var row = document.createElement('div');
        row.className = 'rp-row';
        row.addEventListener('click', function () {
            pt.expanded = !pt.expanded;
            if (pt.expanded) pt._justExpanded = true;
            render();
        });

        // Тег типа
        row.innerHTML += '<div class="rp-tag">' + cfg.label + '</div>';

        // Адрес
        var addrClass = pt.address ? 'rp-addr' : 'rp-addr is-empty';
        row.innerHTML += '<div class="' + addrClass + '">' + (pt.address || 'Укажите адрес') + '</div>';

        // Мета-чипы
        var metaHtml = '<div class="rp-meta">';
        var dateChip = formatDateChip(pt.planned_date);
        if (dateChip) metaHtml += '<span class="rp-chip">' + dateChip + '</span>';
        var loadLabel = LOAD_LABELS[pt.loading_type];
        if (loadLabel) metaHtml += '<span class="rp-chip">' + loadLabel + '</span>';
        metaHtml += '</div>';
        row.innerHTML += metaHtml;

        // Кнопки действий
        var actions = document.createElement('div');
        actions.className = 'rp-actions';
        actions.addEventListener('click', function (e) { e.stopPropagation(); });

        var btnUp = document.createElement('button');
        btnUp.type = 'button';
        btnUp.innerHTML = SVG_UP;
        // Нельзя двигать выше первой позиции, и нельзя ставить выгрузку на позицию 0
        var upBlocked = idx === 0 || (idx === 1 && pt.point_type !== 'LOAD');
        btnUp.disabled = upBlocked;
        btnUp.title = upBlocked && idx === 1 ? 'Первая точка — только погрузка' : 'Вверх';
        btnUp.addEventListener('click', function () { move(idx, -1); });

        var btnDown = document.createElement('button');
        btnDown.type = 'button';
        btnDown.innerHTML = SVG_DOWN;
        // Нельзя двигать ниже последней, и нельзя чтобы выгрузка попала на позицию 0
        var downBlocked = idx === points.length - 1 || (idx === 0 && points[1] && points[1].point_type !== 'LOAD');
        btnDown.disabled = downBlocked;
        btnDown.title = downBlocked && idx === 0 ? 'Первая точка — только погрузка' : 'Вниз';
        btnDown.addEventListener('click', function () { move(idx, 1); });

        actions.appendChild(btnUp);
        actions.appendChild(btnDown);

        var btnDel = document.createElement('button');
        btnDel.type = 'button';
        btnDel.className = 'rp-act-del';
        btnDel.innerHTML = SVG_DEL;
        // Нельзя удалять если останется < 2, и нельзя если выгрузка станет первой
        var delBlocked = points.length <= 2 || (idx === 0 && points[1] && points[1].point_type !== 'LOAD');
        btnDel.disabled = delBlocked;
        if (points.length <= 2) {
            btnDel.title = 'Минимум 2 точки маршрута';
        } else if (delBlocked) {
            btnDel.title = 'Первая точка — только погрузка';
        } else {
            btnDel.title = 'Удалить';
            btnDel.addEventListener('click', function () { remove(idx); });
        }
        actions.appendChild(btnDel);

        row.appendChild(actions);

        // Шеврон
        var chev = document.createElement('div');
        chev.className = 'rp-chev' + (pt.expanded ? ' is-open' : '');
        chev.innerHTML = SVG_CHEV;
        row.appendChild(chev);

        card.appendChild(row);

        // Развёрнутое содержимое
        if (pt.expanded) {
            var detail = renderDetail(pt, idx, cfg);
            card.appendChild(detail);
        }

        div.appendChild(card);
        return div;
    }

    function renderDetail(pt, idx, cfg) {
        var detail = document.createElement('div');
        detail.className = 'rp-detail' + (pt._justExpanded ? ' rp-detail--animate' : '');
        delete pt._justExpanded;

        var errors = pt.errors || {};

        // Ряд 1: Адрес (2fr) | Дата (1fr) | Тип погрузки (1fr)
        var row1 = document.createElement('div');
        row1.className = 'rp-grid-top';
        row1.appendChild(makeField('address', 'Адрес', 'text', pt.address, idx, true, errors.address, 'Город, улица, дом'));
        row1.appendChild(makeField('planned_date', 'Дата и время', 'datetime-local', pt.planned_date, idx, true, errors.planned_date));
        row1.appendChild(makeSelectField('loading_type', 'Тип погрузки', pt.loading_type, idx, [
            { value: '', label: '—' },
            { value: 'rear', label: 'Задняя' },
            { value: 'side', label: 'Боковая' },
            { value: 'top', label: 'Верхняя' },
        ], errors.loading_type));

        // Ряд 2: Организация (1fr) | Контакт имя (1fr) | Контакт телефон (1fr)
        var row2 = document.createElement('div');
        row2.className = 'rp-grid-bottom';
        row2.appendChild(makeOrgField(cfg.orgLabel, pt, idx, errors.organization));
        row2.appendChild(makeField('contact_name', 'Контакт (имя)', 'text', pt.contact_name, idx, false, errors.contact_name, 'ФИО'));
        row2.appendChild(makeField('contact_phone', 'Контакт (телефон)', 'tel', pt.contact_phone, idx, false, errors.contact_phone));

        detail.appendChild(row1);
        detail.appendChild(row2);

        // Инициализация address suggest после добавления в DOM
        requestAnimationFrame(function () {
            initAddressSuggestForField('rp-address-' + idx);
            if (window.PhoneMask) PhoneMask.init(document.getElementById('rp-contact_phone-' + idx));
        });

        return detail;
    }

    function makeField(name, label, type, value, idx, required, fieldErrors, placeholder) {
        var fg = document.createElement('div');
        fg.className = 'rp-field' + (fieldErrors ? ' has-error' : '');

        var lbl = document.createElement('label');
        lbl.setAttribute('for', 'rp-' + name + '-' + idx);
        lbl.innerHTML = label + (required ? '<span class="rp-req">*</span>' : '');

        var input = document.createElement('input');
        input.type = type;
        input.id = 'rp-' + name + '-' + idx;
        input.value = value || '';
        if (placeholder) input.placeholder = placeholder;
        if (type === 'tel') input.setAttribute('data-phone-mask', '');

        input.addEventListener('input', function () {
            points[idx][name] = input.value;
            syncHidden();
            // Обновляем мета в свёрнутой строке без полного ре-рендера
            updateRowMeta(idx);
        });

        fg.appendChild(lbl);
        fg.appendChild(input);

        if (fieldErrors) {
            fieldErrors.forEach(function (err) {
                var errEl = document.createElement('div');
                errEl.className = 'rp-field-error';
                errEl.textContent = err;
                fg.appendChild(errEl);
            });
        }

        return fg;
    }

    function makeSelectField(name, label, value, idx, options, fieldErrors) {
        var fg = document.createElement('div');
        fg.className = 'rp-field' + (fieldErrors ? ' has-error' : '');

        var lbl = document.createElement('label');
        lbl.setAttribute('for', 'rp-' + name + '-' + idx);
        lbl.textContent = label;

        var select = document.createElement('select');
        select.id = 'rp-' + name + '-' + idx;
        options.forEach(function (opt) {
            var o = document.createElement('option');
            o.value = opt.value;
            o.textContent = opt.label;
            if (opt.value === value) o.selected = true;
            select.appendChild(o);
        });

        select.addEventListener('change', function () {
            points[idx][name] = select.value;
            syncHidden();
            updateRowMeta(idx);
        });

        fg.appendChild(lbl);
        fg.appendChild(select);

        if (fieldErrors) {
            fieldErrors.forEach(function (err) {
                var errEl = document.createElement('div');
                errEl.className = 'rp-field-error';
                errEl.textContent = err;
                fg.appendChild(errEl);
            });
        }

        return fg;
    }

    function makeOrgField(label, pt, idx, fieldErrors) {
        var fg = document.createElement('div');
        fg.className = 'rp-field' + (fieldErrors ? ' has-error' : '');

        var lbl = document.createElement('label');
        lbl.setAttribute('for', 'rp-org-' + idx);
        lbl.textContent = label;

        // Скрытый select для autocomplete
        var select = document.createElement('select');
        select.id = 'rp-org-' + idx;
        select.setAttribute('data-search-url', orgSearchUrl);

        // Пустой option
        var emptyOpt = document.createElement('option');
        emptyOpt.value = '';
        emptyOpt.textContent = '';
        select.appendChild(emptyOpt);

        // Текущее значение
        if (pt.organization) {
            var opt = document.createElement('option');
            opt.value = pt.organization;
            opt.textContent = pt.organization_name || ('Организация #' + pt.organization);
            opt.selected = true;
            select.appendChild(opt);
        }

        select.addEventListener('change', function () {
            points[idx].organization = select.value || '';
            var selOpt = select.options[select.selectedIndex];
            points[idx].organization_name = selOpt ? selOpt.text : '';
            syncHidden();
        });

        fg.appendChild(lbl);
        fg.appendChild(select);

        if (fieldErrors) {
            fieldErrors.forEach(function (err) {
                var errEl = document.createElement('div');
                errEl.className = 'rp-field-error';
                errEl.textContent = err;
                fg.appendChild(errEl);
            });
        }

        // Инициализация autocomplete после добавления в DOM
        requestAnimationFrame(function () {
            if (typeof initAutocomplete === 'function') {
                initAutocomplete('rp-org-' + idx);
            }
        });

        return fg;
    }

    // ── Обновление мета в строке без полного ре-рендера ──
    function updateRowMeta(idx) {
        var pt = points[idx];
        var rpEl = container.querySelectorAll('.rp')[idx];
        if (!rpEl) return;

        // Адрес
        var addrEl = rpEl.querySelector('.rp-addr');
        if (addrEl) {
            if (pt.address) {
                addrEl.textContent = pt.address;
                addrEl.classList.remove('is-empty');
            } else {
                addrEl.textContent = 'Укажите адрес';
                addrEl.classList.add('is-empty');
            }
        }

        // Мета-чипы
        var metaEl = rpEl.querySelector('.rp-meta');
        if (metaEl) {
            var html = '';
            var dateChip = formatDateChip(pt.planned_date);
            if (dateChip) html += '<span class="rp-chip">' + dateChip + '</span>';
            var loadLabel = LOAD_LABELS[pt.loading_type];
            if (loadLabel) html += '<span class="rp-chip">' + loadLabel + '</span>';
            metaEl.innerHTML = html;
        }
    }

    // ── Действия ──
    function move(idx, dir) {
        var j = idx + dir;
        if (j < 0 || j >= points.length) return;
        var tmp = points[idx];
        points[idx] = points[j];
        points[j] = tmp;
        render();
    }

    function remove(idx) {
        points.splice(idx, 1);
        render();
    }

    function scrollToLast() {
        var allPts = container.querySelectorAll('.rp');
        if (allPts.length) {
            allPts[allPts.length - 1].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    // ── Синхронизация hidden input ──
    function syncHidden() {
        if (!hiddenInput) return;
        // Очищаем внутренние поля перед отправкой
        var clean = points.map(function (pt, idx) {
            // Достаём чистый телефон из маски (E.164 без +)
            var phoneRaw = '';
            var phoneInput = document.getElementById('rp-contact_phone-' + idx);
            if (phoneInput && phoneInput._phoneMask) {
                var digits = phoneInput._phoneMask.unmaskedValue;
                if (digits.length === 10) phoneRaw = '7' + digits;
            } else {
                phoneRaw = (pt.contact_phone || '').replace(/\D/g, '');
            }
            return {
                point_type: pt.point_type,
                address: pt.address || '',
                planned_date: pt.planned_date || '',
                organization: pt.organization || '',
                loading_type: pt.loading_type || '',
                contact_name: pt.contact_name || '',
                contact_phone: phoneRaw,
            };
        });
        hiddenInput.value = JSON.stringify(clean);
    }

    // ── Address suggest для динамических полей ──
    function initAddressSuggestForField(inputId) {
        if (!addressSuggestUrl) return;
        var input = document.getElementById(inputId);
        if (!input || input.dataset.asSuggestInit) return;
        input.dataset.asSuggestInit = '1';

        var wrapper = document.createElement('div');
        wrapper.className = 'address-suggest-wrap';
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        var list = document.createElement('div');
        list.className = 'address-suggest-list';
        wrapper.appendChild(list);

        var controller = null;
        var debounceTimer = null;

        function closeList() {
            list.style.display = 'none';
            list.innerHTML = '';
        }

        input.addEventListener('input', function () {
            clearTimeout(debounceTimer);
            var q = input.value.trim();
            if (q.length < 3) { closeList(); return; }

            debounceTimer = setTimeout(function () {
                if (controller) controller.abort();
                controller = new AbortController();

                fetch(addressSuggestUrl + '?q=' + encodeURIComponent(q), { signal: controller.signal })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        var items = data && data.suggestions ? data.suggestions.slice(0, 5) : [];
                        list.innerHTML = '';
                        if (!items.length) { closeList(); return; }
                        items.forEach(function (item) {
                            var el = document.createElement('div');
                            el.className = 'address-suggest-item';
                            el.textContent = item.value;
                            el.addEventListener('mousedown', function (e) {
                                e.preventDefault();
                                input.value = item.value;
                                input.dispatchEvent(new Event('input', { bubbles: true }));
                                closeList();
                            });
                            list.appendChild(el);
                        });
                        list.style.display = 'block';
                    })
                    .catch(function (e) {
                        if (e.name !== 'AbortError') closeList();
                    });
            }, 300);
        });

        input.addEventListener('blur', function () {
            setTimeout(closeList, 200);
        });

        document.addEventListener('click', function (e) {
            if (!wrapper.contains(e.target)) closeList();
        });
    }


    // ── Перехватываем сабмит формы ──
    var form = container.closest('form');
    if (form) {
        form.addEventListener('submit', function () {
            syncHidden();
        });
    }

    // ── Начальный рендер ──
    render();

})();
