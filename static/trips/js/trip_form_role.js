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

    // Флаги параметров поиска, управляемые ролью + выбором активного поля.
    // Перестраиваются в dataset.searchUrl через rebuildSearchUrl(). Хранить
    // их отдельно нужно, чтобы setOwnSearch и setExclude могли независимо
    // менять свои куски без необходимости парсить URL.
    //   ownOnly   — autocomplete ищет только среди наших фирм (?own=1).
    //   excludePk — эту организацию исключаем из дропдауна (?exclude=<pk>).
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
        // own=1 может уже быть в базовом URL (forwarder, см. trips/forms.py)
        // — не дублируем.
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
        // Autocomplete.js читает dataset.searchUrl динамически при каждом
        // запросе, так что апдейт срабатывает сразу.
        el.dataset.searchUrl = url;
    }

    // У поля активной роли дропдаун со списком наших фирм должен
    // вываливаться сразу при фокусе, а не ждать ввода двух символов.
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

    // Правило исключений (симметричное для client ↔ carrier):
    //   activeRole === 'client'  → значение id_client исключаем из id_carrier;
    //   activeRole === 'carrier' → значение id_carrier исключаем из id_client.
    // Заказчик и перевозчик не могут совпадать (validate_client_cannot_be_carrier).
    // Активная роль гарантирует, что в «своём» поле стоит одна из наших фирм
    // (prefillIfNeeded + blur-страховка); исключение этой фирмы из поля-пары
    // предотвращает ситуацию «выбрал ту же организацию → ошибка валидации
    // на сабмите». Во всех прочих комбинациях exclude очищаем.
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

        syncExclusions();
        syncForwarderCol(newRole);
        updateCards(newRole);
        dispatchRoleChange(newRole);
    }

    // Пересчёт exclude при изменении значения в поле активной роли.
    // autocomplete.js диспатчит 'change' на SELECT при выборе из дропдауна
    // или очистке через ×. Ребилд отрабатывает сразу — следующий запрос
    // в парном поле уже пойдёт с обновлённым ?exclude.
    //   activeRole=client:  change в id_client  → пересчёт exclude для id_carrier;
    //   activeRole=carrier: change в id_carrier → пересчёт exclude для id_client.
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
