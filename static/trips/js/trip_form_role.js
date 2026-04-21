/**
 * Роль навбар-фирмы в рейсе: JS-контроллер формы.
 *
 * Архитектура (Phase 1.5 — role-driven UI)
 * ----------------------------------------
 * Единственный источник истины — activeRole. Менять его могут только:
 *   1) Автодетект при загрузке (bootstrap из серверных значений).
 *   2) Клик пользователя по карточке роли.
 *
 * Карточка роли определяет, в каком из полей участников сидит «моя фирма»,
 * и что показывает финансовый блок. Поле участника — обычный autocomplete,
 * таким же, как было. Отличия только у того поля, которое соответствует
 * активной роли:
 *
 *   • Дропдаун ограничен нашими фирмами (?own=1). Пользователь может
 *     выбрать другую нашу фирму (если их несколько), но не внешнего
 *     контрагента.
 *   • Значение никогда не пустое: если выбрана роль — поле ВСЕГДА
 *     содержит одну из наших фирм. При переключении карточки, а также
 *     в качестве страховки после blur-инвалидации — перезаливается в
 *     orgId (pk навбар-фирмы).
 *   • Кнопка × скрыта через CSS (.is-role-locked .autocomplete-clear),
 *     чтобы пользователь не мог оставить поле пустым.
 *
 * Неактивные поля участников — обычный поиск по всем организациям
 * (внешние контрагенты). Их значения мы не трогаем.
 *
 * Финансовый блок
 * ---------------
 * trip_form_finance_role.js слушает CustomEvent('trip-role-change') на
 * document и перерисовывается ИСКЛЮЧИТЕЛЬНО по роли, независимо от того,
 * какую именно нашу фирму пользователь выбрал в активном поле.
 *
 * Роль всегда выбрана
 * -------------------
 * При создании: default = client; если у аккаунта есть хоть одно ТС —
 * default = carrier. При редактировании: Trip.perspective (= компьют роли
 * из полей) — если совпало, берём эту роль. Если viewer не участник
 * (observer) — фолбэк на роль по умолчанию по тем же правилам что и для
 * create. Полноценный read-only режим для observer — Task #6.
 *
 * Почему так, а не как было
 * -------------------------
 * Прежняя реализация слушала change/blur на полях участников и
 * пересчитывала роль «по факту значения». Это породило два класса
 * багов: во время набора текста hidden select кратко пустел → роль
 * считалась observer → финансовый блок флипал; и после полного
 * стирания поля форма застревала в «observer при визуально активной
 * карточке». Обе проблемы исчезают, когда поток становится
 * одностороным: роль → поля + ограничения, а не наоборот.
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

    // Базовые search-URL селектов до наших модификаций. Нужны, чтобы на
    // неактивную роль возвращать полный поиск без ?own=1.
    var baseSearchUrl = {};
    ['id_client', 'id_carrier'].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) baseSearchUrl[id] = el.dataset.searchUrl || '';
    });

    // ── Pure function — зеркало trips.roles.compute_trip_role ──
    function computeTripRole(clientId, carrierId, forwarderId, viewerOrgId) {
        if (viewerOrgId == null || viewerOrgId === '') return 'observer';
        var v = String(viewerOrgId);
        if (forwarderId && String(forwarderId) === v) return 'forwarder';
        if (clientId && String(clientId) === v) return 'client';
        if (carrierId && String(carrierId) === v) return 'carrier';
        return 'observer';
    }

    // activeRole всегда одна из 'client' | 'carrier' | 'forwarder'.
    // null бывает только до первого applyRole на этапе инициализации.
    var activeRole = null;

    function isOwnOrg(val) {
        if (!val) return false;
        var s = String(val);
        return ownOrgIds.indexOf(s) !== -1;
    }

    function getField(inputId) {
        var el = document.getElementById(inputId);
        return el ? el.closest('.field') : null;
    }

    // Переключить endpoint поиска у селекта на own=1 (или снять ограничение).
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

    // Гарантировать, что в <select>/hidden input лежит одна из наших фирм.
    // Если уже лежит какая-то наша — оставляем (пользователь мог выбрать
    // другую из своих). Если пусто или чужая — выставляем orgId (навбар).
    function ensureOrgOption(select) {
        if (!select || select.tagName !== 'SELECT') return;
        var exists = Array.from(select.options).some(function (o) {
            return String(o.value) === String(orgId);
        });
        if (!exists) select.add(new Option(orgName, orgId));
    }

    function enforceOwnFirm(inputId) {
        var el = document.getElementById(inputId);
        if (!el) return;
        if (isOwnOrg(el.value)) return;
        if (el.tagName === 'SELECT') {
            ensureOrgOption(el);
            el.value = orgId;
            // change → autocomplete.js синхронизирует видимый input и ×.
            el.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
            // hidden input (forwarder).
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
    // Для client/carrier:
    //   активная роль  → ?own=1, is-role-locked, enforceOwnFirm
    //   другая роль    → базовый search, без лока, значение не трогаем
    // Для forwarder (hidden input без autocomplete):
    //   активная роль  → hidden input = orgId (если ещё не наша)
    //   другая роль    → hidden input = ''
    function applyRole(newRole) {
        activeRole = newRole;

        ['client', 'carrier'].forEach(function (r) {
            var inputId = ROLE_TO_INPUT[r];
            var field = getField(inputId);
            var active = (r === newRole);
            setOwnSearch(inputId, active);
            if (field) field.classList.toggle('is-role-locked', active);
            if (active) enforceOwnFirm(inputId);
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
    //   Повторный клик по активной — no-op (роль нельзя «снять»:
    //   требование UX «роль всегда выбрана»).
    cards.forEach(function (card) {
        card.addEventListener('click', function () {
            var role = card.dataset.role;
            if (activeRole !== role) applyRole(role);
        });
    });

    // ── Страховка: поле активной роли не должно остаться пустым после
    // blur'а с невалидным текстом ──
    //
    // autocomplete.js во время набора кратко очищает select.value. Если
    // пользователь уходит с поля, не выбрав ничего из дропдауна (и
    // 200ms-авто-select не сработал — например, он специально стёр всё),
    // select остаётся пустым. Роль при этом активна, и контракт «поле
    // активной роли — одна из наших фирм» ломается. Здесь мы его
    // восстанавливаем: через небольшой таймаут после blur проверяем поле
    // активной роли и если оно невалидно — перезаливаем в orgId.
    //
    // Важно: это НЕ reverse-flow. Мы не меняем activeRole на основании
    // значения поля; мы, наоборот, приводим поле в соответствие с ролью.
    ['id_client', 'id_carrier'].forEach(function (id) {
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
    //   Edit-mode с данными: computeTripRole; если observer — фолбэк.
    //   Create-mode (форма пустая): hasVehicles ? carrier : client.
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
        // Observer edit-mode (viewer не участник) — выбираем default.
        // Полноценный read-only режим появится в Task #6; до тех пор
        // это фолбэк, не оставляющий интерфейс без активной карточки.
        startRole = (detected === 'observer') ? defaultRole() : detected;
    }
    applyRole(startRole);
});
