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
 *   - поведение дропдауна на фокус: у активного поля дропдаун с нашими
 *     фирмами вываливается сразу при фокусе (флаг openOnFocusAlways).
 *     Наших фирм обычно немного — выбор быстрее, чем набор.
 *
 * Поле-autocomplete в остальном ведёт себя как обычно: пользователь
 * свободно печатает и выбирает. Две тонкости, вытекающие из того, что
 * роль задана и значение обязательно:
 *   1) При активации карточки, если в целевом поле ещё нет нашей фирмы,
 *      оно предзаполняется навбар-фирмой (orgId).
 *   2) После blur'а поле активной роли не может остаться пустым либо
 *      с чужой фирмой — если так случилось (× при незагрузившемся
 *      дропдауне, несовпавший ввод) — возвращаем orgId.
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
    // на неактивную роль возвращать базовый поиск.
    // Для client/carrier base — полный org-поиск (внешние контрагенты
    // разрешены, ?own=1 добавляется только когда роль активна).
    // Для forwarder base уже содержит ?own=1 (экспедитор всегда только
    // из наших фирм на уровне формы — см. trips/forms.py); setOwnSearch
    // не дублирует параметр.
    var baseSearchUrl = {};
    ['id_client', 'id_carrier', 'id_forwarder'].forEach(function (id) {
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
    // Вместе с этим выставляется/снимается openOnFocusAlways='1': у поля
    // активной роли дропдаун со списком наших фирм должен вываливаться
    // сразу при фокусе, а не ждать ввода двух символов.
    function setOwnSearch(inputId, ownOnly) {
        var el = document.getElementById(inputId);
        if (!el) return;
        var base = baseSearchUrl[inputId] || '';
        if (!base) return;
        if (ownOnly) {
            // Если ?own=1 уже в базовом URL (как у forwarder на уровне
            // формы — см. trips/forms.py), не дублируем параметр.
            if (base.indexOf('own=1') !== -1) {
                el.dataset.searchUrl = base;
            } else {
                el.dataset.searchUrl = base + (base.indexOf('?') === -1 ? '?' : '&') + 'own=1';
            }
            el.dataset.openOnFocusAlways = '1';
        } else {
            el.dataset.searchUrl = base;
            delete el.dataset.openOnFocusAlways;
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
            // Фолбэк на случай не-SELECT (не должен срабатывать в текущей
            // конфигурации — все три поля рендерятся как autocomplete).
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
    //   client/carrier неактивной роли: search URL → базовый,
    //                     значение не трогаем (может быть внешний контрагент).
    //   forwarder неактивной роли: значение очищаем. Экспедитор — всегда
    //                     наша фирма и поле показывается только при
    //                     активной роли «Экспедитор»; не сбрасывая значение,
    //                     мы могли бы сохранить в БД «призрак» предыдущей
    //                     попытки выбора.
    function applyRole(newRole) {
        activeRole = newRole;

        ['client', 'carrier', 'forwarder'].forEach(function (r) {
            var inputId = ROLE_TO_INPUT[r];
            var active = (r === newRole);
            setOwnSearch(inputId, active);
            if (active) {
                prefillIfNeeded(inputId);
            } else if (r === 'forwarder') {
                var el = document.getElementById(inputId);
                if (el && el.value) {
                    el.value = '';
                    if (el.tagName === 'SELECT') {
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
            }
        });

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

    // ── Страховка: поле активной роли не должно остаться пустым ──
    //
    // Когда выбрана карточка роли, соответствующее поле обязано содержать
    // одну из наших фирм. Пользователь может случайно очистить его (× или
    // стереть ввод и уйти, не выбрав из дропдауна). autocomplete.js
    // в своём blur даёт 200ms на авто-select; мы проверяем ПОСЛЕ этого
    // окна и, если поле всё ещё пустое или в нём не наша фирма, возвращаем
    // orgId (навбар-фирму). Это НЕ reverse-flow: роль не меняется, мы
    // лишь восстанавливаем контракт «поле активной роли — наша фирма».
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
        // Observer edit-mode (viewer не участник) — фолбэк на default,
        // чтобы интерфейс не оставался без выбранной роли. Полноценный
        // read-only режим — Task #6.
        startRole = (detected === 'observer') ? defaultRole() : detected;
    }
    applyRole(startRole);
});
