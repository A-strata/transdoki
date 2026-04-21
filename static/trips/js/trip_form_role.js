/**
 * Роль навбар-фирмы в рейсе: JS-контроллер формы.
 *
 * Архитектура
 * -----------
 * Единственный источник истины — activeRole. Менять его могут только:
 *   1) Автодетект при загрузке (bootstrap из серверных значений).
 *   2) Клик пользователя по карточке роли.
 *
 * Карточка роли определяет:
 *   - что показывает финансовый блок (событие trip-role-change),
 *   - видимость колонки «Экспедитор»,
 *   - источник поиска в autocomplete для поля, соответствующего роли:
 *     активная роль → ?own=1 (в дропдауне только наши фирмы);
 *     остальные     → базовый поиск (все организации, в т.ч. внешние
 *     контрагенты).
 *
 * Поле-autocomplete в остальном ведёт себя как обычно: пользователь
 * свободно печатает, выбирает, очищает кнопкой ×, в том числе в поле
 * активной роли. Единственное, где роль касается значения поля — это
 * момент активации карточки: в этот момент, если в целевом поле нет
 * нашей фирмы, оно предзаполняется навбар-фирмой (orgId). После этого
 * контроллер в поля не вмешивается — никаких listener'ов на change/blur.
 *
 * Финансовый блок зависит ТОЛЬКО от активной роли, а не от того, какую
 * именно фирму (из нескольких наших) пользователь выбрал в поле.
 *
 * Роль всегда выбрана
 * -------------------
 * Create: default = 'client'; если у аккаунта есть хоть одно ТС — 'carrier'.
 * Edit:   computeTripRole(поля, viewer). Если viewer не участник (observer) —
 *         фолбэк на тот же default. Полноценный read-only режим для observer —
 *         Task #6.
 *
 * Почему так, а не как было
 * -------------------------
 * Прежняя реализация слушала change/blur на полях участников и
 * пересчитывала роль «по факту значения». Это порождало баги: во время
 * набора текста hidden select кратко пустел → роль считалась observer →
 * финансовый блок флипал посреди редактирования. Поток теперь
 * односторонний: роль → ограничения поиска + (одноразовое) предзаполнение.
 *
 * Зеркало серверной функции
 * -------------------------
 * computeTripRole(...) дублирует trips.roles.compute_trip_role и
 * используется только на bootstrap. Любое изменение серверной функции
 * требует правки здесь + tests_roles.py.
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

    // Базовые search-URL селектов до наших модификаций. Нужны, чтобы
    // неактивную роль возвращать на полный поиск без ?own=1.
    var baseSearchUrl = {};
    ['id_client', 'id_carrier'].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) baseSearchUrl[id] = el.dataset.searchUrl || '';
    });

    function computeTripRole(clientId, carrierId, forwarderId, viewerOrgId) {
        if (viewerOrgId == null || viewerOrgId === '') return 'observer';
        var v = String(viewerOrgId);
        if (forwarderId && String(forwarderId) === v) return 'forwarder';
        if (clientId && String(clientId) === v) return 'client';
        if (carrierId && String(carrierId) === v) return 'carrier';
        return 'observer';
    }

    var activeRole = null;  // будет установлена в applyRole из bootstrap

    function isOwnOrg(val) {
        if (!val) return false;
        return ownOrgIds.indexOf(String(val)) !== -1;
    }

    // Переключить endpoint autocomplete-поиска у селекта на ?own=1 или
    // вернуть на базовый. Autocomplete.js читает dataset.searchUrl
    // динамически при каждом запросе, так что апдейт срабатывает сразу.
    function setOwnSearch(inputId, ownOnly) {
        var el = document.getElementById(inputId);
        if (!el) return;
        var base = baseSearchUrl[inputId] || '';
        if (!base) return;
        if (ownOnly) {
            el.dataset.searchUrl = base + (base.indexOf('?') === -1 ? '?' : '&') + 'own=1';
        } else {
            el.dataset.searchUrl = base;
        }
    }

    // Одноразовое предзаполнение при активации роли: если в поле нет
    // нашей фирмы — пишем туда orgId (pk навбар-фирмы). Если наша уже
    // стоит — оставляем (пользователь мог выбрать другую свою фирму).
    // После этого момента в поле больше не вмешиваемся.
    function ensureOrgOption(select) {
        if (!select || select.tagName !== 'SELECT') return;
        var exists = Array.from(select.options).some(function (o) {
            return String(o.value) === String(orgId);
        });
        if (!exists) select.add(new Option(orgName, orgId));
    }

    function prefillIfNeeded(inputId) {
        var el = document.getElementById(inputId);
        if (!el) return;
        if (isOwnOrg(el.value)) return;
        if (el.tagName === 'SELECT') {
            ensureOrgOption(el);
            el.value = orgId;
            // change → autocomplete.js синхронизирует видимый input и ×.
            el.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
            // hidden input (forwarder)
            el.value = orgId;
        }
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
            c.classList.toggle('is-active', c.dataset.role === role);
        });
    }

    function dispatchRoleChange(role) {
        document.dispatchEvent(new CustomEvent('trip-role-change', { detail: { role: role } }));
    }

    // ── Главный мутатор ──
    //   active role поле: search URL → ?own=1, предзаполнить нашей фирмой
    //                     (если ещё не наша).
    //   другие роли поля: search URL → базовый, значение не трогаем.
    //   forwarder (hidden input без autocomplete): orgId при активной,
    //                     пусто при любой другой.
    function applyRole(newRole) {
        activeRole = newRole;

        ['client', 'carrier'].forEach(function (r) {
            var inputId = ROLE_TO_INPUT[r];
            var active = (r === newRole);
            setOwnSearch(inputId, active);
            if (active) prefillIfNeeded(inputId);
        });

        var fwd = document.getElementById('id_forwarder');
        if (fwd) {
            if (newRole === 'forwarder') {
                if (!isOwnOrg(fwd.value)) fwd.value = orgId;
            } else {
                fwd.value = '';
            }
        }

        syncForwarderCol(newRole);
        updateCards(newRole);
        dispatchRoleChange(newRole);
    }

    // ── Клик по карточке ──
    //   Роль всегда выбрана, поэтому повторный клик по активной — no-op.
    cards.forEach(function (card) {
        card.addEventListener('click', function () {
            var role = card.dataset.role;
            if (activeRole !== role) applyRole(role);
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
        // Observer edit-mode (viewer не участник) — фолбэк на default,
        // чтобы интерфейс не оставался без выбранной роли. Полноценный
        // read-only режим — Task #6.
        startRole = (detected === 'observer') ? defaultRole() : detected;
    }
    applyRole(startRole);
});
