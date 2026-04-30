/**
 * Роль навбар-фирмы в рейсе: JS-контроллер формы.
 *
 * Архитектура (двумерное состояние)
 * ----------------------------------
 * Состояние формы — пара (activeRole, forwarderEnabled):
 *
 *   activeRole       ∈ { client, carrier, forwarder }
 *       Какую роль навбар-фирма играет в рейсе. Источник истины — карточка
 *       роли. Bootstrap: detected role из серверных значений; observer
 *       откатывается на default.
 *
 *   forwarderEnabled ∈ { false, true }
 *       Только для activeRole в { client, carrier }: означает «в рейсе
 *       присутствует внешний экспедитор как отдельное звено цепочки».
 *       При activeRole === 'forwarder' принудительно false (бессмыслен —
 *       мы сами экспедитор).
 *
 *       ВАЖНО про carrier-роль: UI-управление (тоггл) есть только в
 *       карточке client. У carrier тоггла нет осознанно — трёхзвенный
 *       рейс под навбаром перевозчика out-of-scope MVP. Поэтому в
 *       carrier-роли forwarderEnabled может стать true только на
 *       bootstrap-е существующего рейса с уже заполненным forwarder
 *       (создан под другой own-фирмой). State-машина это поддерживает
 *       без специальных веток — поле редактируемо как любое другое,
 *       очистка через × естественным образом сводит cycle к двухзвенному.
 *
 * Видимость колонки «Экспедитор» (parties-forwarder-col):
 *   activeRole === 'forwarder'                                 → показана
 *   activeRole в {client, carrier} && forwarderEnabled         → показана
 *   activeRole в {client, carrier} && !forwarderEnabled        → скрыта
 *
 * Поведение поля forwarder:
 *   activeRole === 'forwarder':
 *       - search ?own=1, openOnFocusAlways (только наши фирмы)
 *       - inline-create запрещён (создавать «свою» фирму нельзя из формы)
 *       - prefill навбар-фирмой (карточка = «навбар играет эту роль»)
 *   activeRole в {client, carrier} && forwarderEnabled:
 *       - search без ?own=1 (любая организация аккаунта)
 *       - inline-create разрешён (можно добавить нового внешнего)
 *       - prefill отсутствует (пользователь явно выбирает звено цепочки)
 *   activeRole в {client, carrier} && !forwarderEnabled:
 *       - значение поля очищается, колонка скрыта
 *
 * Источник истины — DOM. forwarderEnabled нигде не персистится отдельно;
 * на bootstrap выводится из правила «forwarder задан ∧ detected role
 * ≠ forwarder». При сабмите с form-валидацией провалом сервер ре-рендерит
 * с теми же значениями полей, и логика восстанавливается симметрично.
 *
 * Зеркало серверной функции
 * -------------------------
 * computeTripRole(...) дублирует trips.roles.compute_trip_role и
 * используется только на bootstrap. Любое изменение серверной функции
 * требует правки здесь + tests_roles.py.
 *
 * Карточки — div с role=button
 * ----------------------------
 * Раньше карточки были <button>. Внутрь карточки теперь вкладывается
 * <input type=checkbox> (тоггл «Привлекаю экспедитора» / «Работаю через
 * экспедитора»), а вложенный input внутри button невалиден по HTML и
 * приводит к двойному срабатыванию click (button → checkbox → bubble
 * обратно к button). Поэтому карточка стала <div role="button"
 * tabindex="0">, а активация по Enter/Space реализована вручную в
 * keydown-обработчике. Стилизация в CSS — по классу .role-card,
 * её смена тега не затрагивает.
 */
document.addEventListener('DOMContentLoaded', function () {
    var config = document.getElementById('role-config');
    if (!config) return;

    var orgId = config.dataset.orgId;
    var orgName = config.dataset.orgName;
    var hasVehicles = config.dataset.hasVehicles === 'true';
    var ownOrgIds = (config.dataset.ownOrgIds || '')
        .split(',')
        .map(function (s) { return s.trim(); })
        .filter(Boolean);

    var cards = document.querySelectorAll('.role-card');
    var ROLE_TO_INPUT = {
        client: 'id_client',
        carrier: 'id_carrier',
        forwarder: 'id_forwarder',
    };

    // Базовые search-URL и ac-create — заданные сервером в forms.py.
    // baseSearchUrl: для client/carrier — обычный org-поиск; для
    // forwarder с Этапа 2 — тоже обычный (?own=1 теперь добавляется
    // динамически только когда роль = forwarder).
    // baseAcCreate: '1' для всех трёх (forwarder тоже — нужен на роли
    // client/carrier с включённым тоггом «внешний экспедитор»). На роли
    // forwarder снимаем динамически.
    var baseSearchUrl = {};
    var baseAcCreate = {};
    ['id_client', 'id_carrier', 'id_forwarder'].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) {
            baseSearchUrl[id] = el.dataset.searchUrl || '';
            baseAcCreate[id] = el.dataset.acCreate || '';
        }
    });

    function computeTripRole(clientId, carrierId, forwarderId, viewerOrgId) {
        if (viewerOrgId == null || viewerOrgId === '') return 'observer';
        var v = String(viewerOrgId);
        if (forwarderId && String(forwarderId) === v) return 'forwarder';
        if (clientId && String(clientId) === v) return 'client';
        if (carrierId && String(carrierId) === v) return 'carrier';
        return 'observer';
    }

    var activeRole = null;
    var forwarderEnabled = false;

    function isOwnOrg(val) {
        if (!val) return false;
        return ownOrgIds.indexOf(String(val)) !== -1;
    }

    var searchFlags = {
        id_client: { ownOnly: false, excludePk: '' },
        id_carrier: { ownOnly: false, excludePk: '' },
        id_forwarder: { ownOnly: false, excludePk: '' },
    };

    function rebuildSearchUrl(inputId) {
        var el = document.getElementById(inputId);
        if (!el) return;
        var base = baseSearchUrl[inputId] || '';
        if (!base) return;
        var flags = searchFlags[inputId] || {};
        var params = [];
        if (flags.ownOnly && base.indexOf('own=1') === -1) {
            params.push('own=1');
        }
        if (flags.excludePk) {
            params.push('exclude=' + encodeURIComponent(flags.excludePk));
        }
        var url = base;
        if (params.length) {
            url += (base.indexOf('?') === -1 ? '?' : '&') + params.join('&');
        }
        el.dataset.searchUrl = url;
    }

    function setOwnSearch(inputId, ownOnly) {
        var flags = searchFlags[inputId];
        if (!flags) return;
        flags.ownOnly = !!ownOnly;
        var el = document.getElementById(inputId);
        if (el) {
            if (ownOnly) el.dataset.openOnFocusAlways = '1';
            else delete el.dataset.openOnFocusAlways;
        }
        rebuildSearchUrl(inputId);
    }

    function setExclude(inputId, pk) {
        var flags = searchFlags[inputId];
        if (!flags) return;
        flags.excludePk = pk ? String(pk) : '';
        rebuildSearchUrl(inputId);
    }

    function setCreateAllowed(inputId, allowed) {
        var el = document.getElementById(inputId);
        if (!el) return;
        if (allowed && baseAcCreate[inputId] === '1') {
            el.dataset.acCreate = '1';
        } else {
            delete el.dataset.acCreate;
        }
    }

    // Заказчик и перевозчик не могут совпадать
    // (validate_client_cannot_be_carrier). Активная роль гарантирует, что
    // в «своём» поле стоит одна из наших фирм, поэтому исключаем её
    // из дропдауна парного поля. Для forwarder exclude не делаем — поле
    // принимает любую org аккаунта, валидаторы проверят равенство потом.
    function syncExclusions() {
        setExclude('id_client', '');
        setExclude('id_carrier', '');
        setExclude('id_forwarder', '');
        if (activeRole === 'client') {
            var clientEl = document.getElementById('id_client');
            if (clientEl && clientEl.value) {
                setExclude('id_carrier', clientEl.value);
            }
        } else if (activeRole === 'carrier') {
            var carrierEl = document.getElementById('id_carrier');
            if (carrierEl && carrierEl.value) {
                setExclude('id_client', carrierEl.value);
            }
        }
    }

    function ensureOrgOption(select) {
        if (!select || select.tagName !== 'SELECT') return;
        var exists = Array.from(select.options).some(function (o) {
            return String(o.value) === String(orgId);
        });
        if (!exists) select.add(new Option(orgName, orgId));
    }

    function prefillIfNeeded(inputId, force) {
        var el = document.getElementById(inputId);
        if (!el) return;
        if (String(el.value) === String(orgId)) return;
        if (!force && isOwnOrg(el.value)) return;
        if (el.tagName === 'SELECT') {
            ensureOrgOption(el);
            el.value = orgId;
            el.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
            el.value = orgId;
        }
    }

    function clearField(inputId) {
        var el = document.getElementById(inputId);
        if (!el) return;
        if (el.value) {
            el.value = '';
            if (el.tagName === 'SELECT') {
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
    }

    var partiesGrid = document.getElementById('parties-grid');
    var forwarderCol = document.getElementById('parties-forwarder-col');

    function syncForwarderCol() {
        if (!partiesGrid || !forwarderCol) return;
        var visible = activeRole === 'forwarder' ||
            ((activeRole === 'client' || activeRole === 'carrier') && forwarderEnabled);
        forwarderCol.hidden = !visible;
        partiesGrid.classList.toggle('parties-grid--with-forwarder', visible);
    }

    function syncForwarderField() {
        var roleIsForwarder = activeRole === 'forwarder';
        var roleIsParticipant = activeRole === 'client' || activeRole === 'carrier';
        setOwnSearch('id_forwarder', roleIsForwarder);
        setCreateAllowed('id_forwarder', roleIsParticipant && forwarderEnabled);
    }

    function updateCards() {
        cards.forEach(function (c) {
            var isActive = c.dataset.role === activeRole;
            c.classList.toggle('is-active', isActive);
            c.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });
    }

    function syncToggleCheckboxes() {
        document.querySelectorAll('[data-role-toggle="forwarder"]').forEach(function (cb) {
            cb.checked = forwarderEnabled;
        });
    }

    function dispatchRoleChange() {
        document.dispatchEvent(new CustomEvent('trip-role-change', {
            detail: { role: activeRole, forwarderEnabled: forwarderEnabled }
        }));
    }

    /**
     * Главный мутатор. Принимает любые комбинации role / forwarderEnabled.
     * Семантика:
     *   role не задан → оставляем текущую активную роль
     *   forwarderEnabled не задан → оставляем текущий, но при userInitiated
     *       смене роли принудительно сбрасываем (UX: новая роль начинается
     *       с чистого листа, чтобы предыдущая «открытая» колонка не
     *       тащилась на новую роль).
     *   role === 'forwarder' → forwarderEnabled принудительно false
     *       (бессмыслен — мы сами экспедитор).
     */
    function applyState(opts) {
        opts = opts || {};
        var prevRole = activeRole;
        var newRole = opts.role !== undefined ? opts.role : activeRole;
        var newFwdEnabled = opts.forwarderEnabled !== undefined
            ? opts.forwarderEnabled : forwarderEnabled;
        var userInitiated = !!opts.userInitiated;

        if (newRole === 'forwarder') {
            newFwdEnabled = false;
        }
        if (userInitiated && newRole !== prevRole && opts.forwarderEnabled === undefined) {
            newFwdEnabled = false;
        }

        activeRole = newRole;
        forwarderEnabled = newFwdEnabled;

        // ── Поля client/carrier ──
        ['client', 'carrier'].forEach(function (r) {
            var inputId = ROLE_TO_INPUT[r];
            var active = (r === activeRole);
            setOwnSearch(inputId, active);
            setCreateAllowed(inputId, !active);
            if (active) {
                prefillIfNeeded(inputId, userInitiated);
                return;
            }
            // Чистим поле предыдущей активной роли только при user-initiated
            // смене и только если там одна из наших фирм (артефакт prefill'а).
            // Внешнего контрагента, явно введённого пользователем, не трогаем.
            var prevEl = document.getElementById(inputId);
            if (userInitiated && r === prevRole && prevEl && isOwnOrg(prevEl.value)) {
                clearField(inputId);
            }
        });

        // ── Поле forwarder ──
        syncForwarderField();
        if (activeRole === 'forwarder') {
            prefillIfNeeded('id_forwarder', userInitiated);
        } else if (!forwarderEnabled) {
            // Колонка скрыта — значение не имеет смысла.
            clearField('id_forwarder');
        }
        // (activeRole в {client, carrier} && forwarderEnabled): значение
        // оставляем — либо bootstrap восстановил серверный forwarder, либо
        // пользователь введёт вручную.

        syncExclusions();
        syncForwarderCol();
        updateCards();
        syncToggleCheckboxes();
        dispatchRoleChange();
    }

    // ── Слушатели изменений в полях для пересчёта exclude ──
    (function bindChangeForExclusions() {
        var clientEl = document.getElementById('id_client');
        if (clientEl) {
            clientEl.addEventListener('change', function () {
                if (activeRole === 'client') syncExclusions();
            });
        }
        var carrierEl = document.getElementById('id_carrier');
        if (carrierEl) {
            carrierEl.addEventListener('change', function () {
                if (activeRole === 'carrier') syncExclusions();
            });
        }
    })();

    // ── Активация карточки ролью (клик / Enter / Space) ──
    function activateCard(card) {
        var role = card.dataset.role;
        if (activeRole !== role) {
            applyState({ role: role, userInitiated: true });
        }
    }

    cards.forEach(function (card) {
        card.addEventListener('click', function (e) {
            // Клик по чекбоксу/лейблу не активирует карточку — иначе
            // bubble привёл бы к двойному эффекту: смена роли + toggle.
            if (e.target.closest('.role-card-toggle')) return;
            activateCard(card);
        });
        card.addEventListener('keydown', function (e) {
            if (e.target.closest('.role-card-toggle')) return;
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                activateCard(card);
            }
        });
    });

    // ── Слушатели чекбоксов «Привлекаю / Работаю через экспедитора» ──
    document.querySelectorAll('[data-role-toggle="forwarder"]').forEach(function (cb) {
        cb.addEventListener('change', function () {
            // Тоггл должен срабатывать только на активной карточке. CSS
            // прячет неактивные тогглы, но защитимся от программного
            // change — иначе stale-чекбокс мог бы изменить состояние.
            var card = cb.closest('.role-card');
            if (!card || !card.classList.contains('is-active')) {
                cb.checked = forwarderEnabled;
                return;
            }
            applyState({
                forwarderEnabled: cb.checked,
                userInitiated: true,
            });
        });
    });

    // ── Страховка: поле активной роли не должно остаться пустым ──
    // Применяется только к id_client/id_carrier/id_forwarder, когда
    // соответствующая роль активна. Для роли client/carrier с тоггом ON
    // forwarder-поле НЕ страхуем: пользователь может намеренно оставить
    // его пустым и форма сохранится без forwarder.
    ['id_client', 'id_carrier', 'id_forwarder'].forEach(function (id) {
        var select = document.getElementById(id);
        if (!select) return;
        var container = select.closest('.autocomplete-container');
        var input = container && container.querySelector('.autocomplete-input');
        if (!input) return;
        input.addEventListener('blur', function () {
            setTimeout(function () {
                if (!activeRole) return;
                if (ROLE_TO_INPUT[activeRole] !== id) return;
                if (!isOwnOrg(select.value)) {
                    ensureOrgOption(select);
                    select.value = orgId;
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }, 300);
        });
    });

    // ── Bootstrap ──
    var clientEl = document.getElementById('id_client');
    var carrierEl = document.getElementById('id_carrier');
    var forwarderEl = document.getElementById('id_forwarder');

    var initialClient = clientEl ? clientEl.value : '';
    var initialCarrier = carrierEl ? carrierEl.value : '';
    var initialForwarder = forwarderEl ? forwarderEl.value : '';
    var isEmptyForm = !initialClient && !initialCarrier && !initialForwarder;

    function defaultRole() {
        return hasVehicles ? 'carrier' : 'client';
    }

    var startRole;
    if (isEmptyForm) {
        startRole = defaultRole();
    } else {
        var detected = computeTripRole(initialClient, initialCarrier, initialForwarder, orgId);
        startRole = (detected === 'observer') ? defaultRole() : detected;
    }

    // forwarderEnabled выводится из факта наличия forwarder при detected
    // роли ≠ forwarder. Покрывает edit-режим: если рейс создан с внешним
    // экспедитором (наша фирма — client/carrier), при загрузке формы
    // тоггл должен быть в положении ON.
    var startFwdEnabled = !!(initialForwarder &&
        (startRole === 'client' || startRole === 'carrier'));

    applyState({ role: startRole, forwarderEnabled: startFwdEnabled });
});
