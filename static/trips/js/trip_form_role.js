/**
 * Роль навбар-фирмы в рейсе: JS-контроллер формы.
 *
 * Архитектура (Phase 1.5 — one-way flow: карточка → поля)
 * -------------------------------------------------------
 * Единственный источник истины — activeRole. Менять его могут только:
 *   1) Автодетект при загрузке (bootstrap из серверных значений).
 *   2) Клик пользователя по карточке роли.
 *
 * Поля участников («моя фирма» для client/carrier/forwarder) — ВЫХОД
 * относительно роли, а не вход. Пока роль активна, соответствующее
 * поле заблокировано: на его месте выводится имя «моей фирмы», а
 * автокомплит (input + кнопка добавления + селект) скрыт. Пользователь
 * не может ни стереть это значение, ни ввести другое — сменить свою
 * фирму можно только через смену карточки роли.
 *
 * Почему так, а не как было
 * -------------------------
 * Прежняя реализация слушала change/blur на селектах участников и
 * пересчитывала роль «по факту значения поля». Это породило два
 * класса багов:
 *
 *   1) Во время набора текста в автокомплите hidden select кратко
 *      очищался — computeTripRole возвращал observer — финансовый
 *      блок флипал в «оба столбца» посреди набора.
 *   2) После полного стирания поля форма застревала в «observer при
 *      визуально активной карточке» и лечилась только перекликом по
 *      карточке.
 *
 * Новая схема убивает оба: поле нельзя стереть, карточка независима
 * от состояния автокомплита. Reverse-flow (change/blur listeners)
 * полностью удалены.
 *
 * Зеркало серверной функции
 * -------------------------
 * computeTripRole(...) дублирует trips.roles.compute_trip_role и
 * используется ТОЛЬКО на старте — автодетект роли из значений,
 * пришедших с сервера (initial в create / instance в update). Любое
 * изменение серверной функции требует правки здесь + tests_roles.py.
 *
 * Предзаполнение
 * --------------
 * При активации роли целевое поле получает orgId (pk навбар-фирмы).
 * По контракту мультитенантности navbar-фирма всегда принадлежит
 * текущему account-у, поэтому «одна наша фирма» и «несколько, выбрана
 * такая-то в навбаре» сводятся к одному правилу: prefill = orgId.
 *
 * Событие
 * -------
 * Диспатчится CustomEvent('trip-role-change', { detail: { role } }) на
 * document. role ∈ { 'client', 'carrier', 'forwarder', null }.
 * null — observer / роль не выбрана — финансовый блок показывает оба
 * столбца (backward-compat). Слушатель в trip_form_finance_role.js.
 */
document.addEventListener('DOMContentLoaded', function () {
    var config = document.getElementById('role-config');
    if (!config) return;

    var orgId = config.dataset.orgId;
    var orgName = config.dataset.orgName;
    var hasVehicles = config.dataset.hasVehicles === 'true';
    // own_org_ids (CSV) доступны через config.dataset.ownOrgIds. Phase 2
    // будет использовать их для фильтрации дропдауна при смене моей фирмы
    // из нескольких. Phase 1.5 завязан на orgId (навбар), поэтому не читает.

    var cards = document.querySelectorAll('.role-card');
    var ROLE_TO_INPUT = {
        client: 'id_client',
        carrier: 'id_carrier',
        forwarder: 'id_forwarder',
    };

    // ────────────────────────────────────────────────────────────────────
    // Pure function — зеркало trips.roles.compute_trip_role.
    // Используется только на bootstrap. Любое изменение серверной
    // функции → правка здесь + tests_roles.py.
    // ────────────────────────────────────────────────────────────────────
    function computeTripRole(clientId, carrierId, forwarderId, viewerOrgId) {
        if (viewerOrgId == null || viewerOrgId === '') return 'observer';
        var v = String(viewerOrgId);
        if (forwarderId && String(forwarderId) === v) return 'forwarder';
        if (clientId && String(clientId) === v) return 'client';
        if (carrierId && String(carrierId) === v) return 'carrier';
        return 'observer';
    }

    // ── Единственное состояние ──
    var activeRole = null;  // 'client' | 'carrier' | 'forwarder' | null

    // ────────────────────────────────────────────────────────────────────
    // Работа с селектом/инпутом «моей фирмы».
    // client/carrier — <select> внутри autocomplete-виджета.
    // forwarder — <input type="hidden"> (без autocomplete).
    // ────────────────────────────────────────────────────────────────────
    function ensureOrgOption(select) {
        if (!select || select.tagName !== 'SELECT') return;
        var exists = Array.from(select.options).some(function (o) {
            return String(o.value) === String(orgId);
        });
        if (!exists) {
            select.add(new Option(orgName, orgId));
        }
    }

    function setInputToOrg(inputId) {
        var el = document.getElementById(inputId);
        if (!el) return;
        if (el.tagName === 'SELECT') {
            ensureOrgOption(el);
            el.value = orgId;
            // Синхронизировать видимый input автокомплита и clear-btn.
            // Даже если контейнер сейчас скрыт (роль активна) — делаем
            // это сразу, чтобы при последующей разблокировке пользователь
            // увидел корректное значение, а не пустое поле.
            el.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
            // hidden input (forwarder) — просто пишем pk.
            el.value = orgId;
        }
    }

    function clearInput(inputId) {
        var el = document.getElementById(inputId);
        if (!el) return;
        if (el.value === '') return;
        el.value = '';
        if (el.tagName === 'SELECT') {
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    // ────────────────────────────────────────────────────────────────────
    // Блокировка/разблокировка поля «моей фирмы».
    //
    // client/carrier: в .field прячем .field-add-row (там autocomplete +
    //   кнопка «+») и вставляем <p data-role-lock> с именем моей фирмы.
    // forwarder: в template уже статическая <p> в колонке
    //   parties-forwarder-col — вся «блокировка» сводится к управлению
    //   видимостью колонки через syncForwarderCol().
    // ────────────────────────────────────────────────────────────────────
    function getField(inputId) {
        var el = document.getElementById(inputId);
        if (!el) return null;
        return el.closest('.field');
    }

    function lockField(inputId) {
        var field = getField(inputId);
        if (!field) return;
        var row = field.querySelector('.field-add-row');
        if (row) row.hidden = true;
        var locked = field.querySelector('[data-role-lock]');
        if (!locked) {
            locked = document.createElement('p');
            locked.className = 'parties-forwarder-name';
            locked.setAttribute('data-role-lock', '1');
            locked.textContent = orgName;
            if (row && row.parentNode) {
                row.parentNode.insertBefore(locked, row);
            } else {
                field.appendChild(locked);
            }
        } else {
            locked.textContent = orgName;
            locked.hidden = false;
        }
        field.classList.add('is-role-locked');
        // Почистить наследие старой «prefilled»-подсветки, если осталась
        // с прошлых сессий рендера.
        field.classList.remove('is-prefilled');
        var hint = field.querySelector('.prefilled-hint');
        if (hint) hint.remove();
    }

    function unlockField(inputId) {
        var field = getField(inputId);
        if (!field) return;
        var row = field.querySelector('.field-add-row');
        if (row) row.hidden = false;
        var locked = field.querySelector('[data-role-lock]');
        if (locked) locked.remove();
        field.classList.remove('is-role-locked');
    }

    var partiesGrid = document.getElementById('parties-grid');
    var forwarderCol = document.getElementById('parties-forwarder-col');

    function syncForwarderCol(role) {
        if (!partiesGrid || !forwarderCol) return;
        var isForwarder = role === 'forwarder';
        forwarderCol.hidden = !isForwarder;
        partiesGrid.classList.toggle('parties-grid--with-forwarder', isForwarder);
    }

    function updateCards(role) {
        cards.forEach(function (c) {
            c.classList.toggle('is-active', role !== null && c.dataset.role === role);
        });
    }

    function dispatchRoleChange(role) {
        document.dispatchEvent(new CustomEvent('trip-role-change', { detail: { role: role } }));
    }

    // ────────────────────────────────────────────────────────────────────
    // Главный мутатор состояния.
    //   - target-поле получает orgId и блокируется (client/carrier).
    //   - остальные поля: если там лежала orgId — очищаем (чтобы не было
    //     двух «моих фирм» одновременно, это ломает computeTripRole и
    //     вводит в заблуждение same-org валидаторы). Любое другое
    //     значение (внешний контрагент) не трогаем.
    //   - остальные client/carrier — разблокируются.
    //   - колонка forwarder синхронизируется отдельно.
    //   - карточки подсвечиваются, событие диспатчится.
    // ────────────────────────────────────────────────────────────────────
    function applyRole(newRole) {
        activeRole = newRole;

        Object.keys(ROLE_TO_INPUT).forEach(function (r) {
            var inputId = ROLE_TO_INPUT[r];
            if (r === newRole) {
                setInputToOrg(inputId);
                if (r !== 'forwarder') lockField(inputId);
            } else {
                var el = document.getElementById(inputId);
                if (el && String(el.value) === String(orgId)) {
                    clearInput(inputId);
                }
                if (r !== 'forwarder') unlockField(inputId);
            }
        });

        syncForwarderCol(newRole);
        updateCards(newRole);
        dispatchRoleChange(newRole);
    }

    function deactivate() {
        activeRole = null;

        Object.keys(ROLE_TO_INPUT).forEach(function (r) {
            var inputId = ROLE_TO_INPUT[r];
            var el = document.getElementById(inputId);
            if (el && String(el.value) === String(orgId)) {
                clearInput(inputId);
            }
            if (r !== 'forwarder') unlockField(inputId);
        });

        syncForwarderCol(null);
        updateCards(null);
        dispatchRoleChange(null);
    }

    // ── Клик по карточке ──
    //   Повторный клик по активной — деактивация; иначе — переход.
    cards.forEach(function (card) {
        card.addEventListener('click', function () {
            var role = card.dataset.role;
            if (activeRole === role) {
                deactivate();
            } else {
                applyRole(role);
            }
        });
    });

    // ────────────────────────────────────────────────────────────────────
    // Bootstrap: автодетект роли из серверных значений.
    //   - Пустая форма + есть ТС → carrier (UX для автопарков).
    //   - Пустая форма без ТС → observer (роль не выбрана).
    //   - Непустая форма → computeTripRole; совпадение → эта роль;
    //     observer → не участник (остаёмся без роли; полноценный
    //     read-only режим появится в Task #6).
    // ────────────────────────────────────────────────────────────────────
    var clientEl = document.getElementById('id_client');
    var carrierEl = document.getElementById('id_carrier');
    var forwarderEl = document.getElementById('id_forwarder');

    var initialClient = clientEl ? clientEl.value : '';
    var initialCarrier = carrierEl ? carrierEl.value : '';
    var initialForwarder = forwarderEl ? forwarderEl.value : '';
    var isEmptyForm = !initialClient && !initialCarrier && !initialForwarder;

    if (isEmptyForm && hasVehicles) {
        applyRole('carrier');
    } else if (isEmptyForm) {
        deactivate();
    } else {
        var detected = computeTripRole(initialClient, initialCarrier, initialForwarder, orgId);
        if (detected === 'observer') {
            deactivate();
        } else {
            applyRole(detected);
        }
    }
});

// EOF
