/**
 * Роль навбар-фирмы в рейсе: JS-контроллер формы.
 *
 * Задача модуля
 * -------------
 * Держать визуальное состояние формы рейса (активная карточка роли,
 * подсветка «подставлено автоматически», видимость колонки «Экспедитор»
 * в блоке участников) в согласии с одним-единственным правилом:
 *
 *     role = f(client_id, carrier_id, forwarder_id, viewer_org_id)
 *
 * Это правило реализовано на сервере как
 * trips.roles.compute_trip_role и используется из Trip.perspective().
 * Здесь живёт ЕГО ЗЕРКАЛО: computeTripRole(...). Поведение обязано
 * совпадать бит-в-бит; любое изменение серверной функции требует
 * правки и тестов в обоих местах.
 *
 * Почему пере-вычисление, а не stateful activeRole
 * ------------------------------------------------
 * Предыдущая версия хранила активную роль в локальной переменной
 * activeRole и слушала input-событие автокомплита, сбрасывая роль в null
 * при каждом нажатии клавиши. Это порождало баг:
 *
 *     Навбар = SL (own, client), ИП Астахин = own carrier.
 *     Редактирую заказчика → в процессе набора селект автокомплита
 *     кратко очищается → activeRole становится null → финансовый блок
 *     уходит в режим «оба столбца» (как если бы я был экспедитором).
 *
 * Корень проблемы — дублирующий источник истины (activeRole + значения
 * полей формы). Теперь источник истины только один: сами значения полей.
 * На любое изменение селектов участников мы пере-вычисляем роль чистой
 * функцией и синхронизируем UI. Никаких input-слушателей на
 * автокомплитах — select меняет value сам (через autocomplete.js,
 * selectItem/clearBtn/invalidation), и этого достаточно.
 *
 * События
 * -------
 * Диспатчится CustomEvent('trip-role-change', { detail: { role } }) на
 * document. role — одна из { 'client', 'carrier', 'forwarder', null }.
 * null соответствует TripRole.OBSERVER — финансовый блок в этом режиме
 * показывает оба столбца (backward-compat). Слушатель — в
 * trip_form_finance_role.js.
 */
document.addEventListener('DOMContentLoaded', function () {
    var config = document.getElementById('role-config');
    if (!config) return;

    var orgId = config.dataset.orgId;
    var orgName = config.dataset.orgName;
    var hasVehicles = config.dataset.hasVehicles === 'true';
    // own_org_ids доступны через config.dataset.ownOrgIds (CSV). Phase 1
    // их не использует; Phase 2 будет фильтровать дропдауны.

    var cards = document.querySelectorAll('.role-card');
    var ROLE_TO_SELECT = {
        client: 'id_client',
        carrier: 'id_carrier',
        forwarder: 'id_forwarder',
    };

    var clientSelect = document.getElementById('id_client');
    var carrierSelect = document.getElementById('id_carrier');
    var forwarderInput = document.getElementById('id_forwarder');

    // ────────────────────────────────────────────────────────────────────
    // Pure function — зеркало trips.roles.compute_trip_role.
    // Любое изменение серверной функции → правка здесь + tests_roles.py.
    // Принимает строки/числа, нормализует к String сравнению.
    // Возвращает 'client' | 'carrier' | 'forwarder' | 'observer'.
    // ────────────────────────────────────────────────────────────────────
    function computeTripRole(clientId, carrierId, forwarderId, viewerOrgId) {
        if (viewerOrgId == null || viewerOrgId === '') return 'observer';
        var v = String(viewerOrgId);
        if (forwarderId && String(forwarderId) === v) return 'forwarder';
        if (clientId && String(clientId) === v) return 'client';
        if (carrierId && String(carrierId) === v) return 'carrier';
        return 'observer';
    }

    function readFormState() {
        return {
            clientId: clientSelect ? clientSelect.value : '',
            carrierId: carrierSelect ? carrierSelect.value : '',
            forwarderId: forwarderInput ? forwarderInput.value : '',
        };
    }

    // ── Вспомогательные: визуальная подсказка «подставлено автоматически» ──
    function getField(selectId) {
        var select = document.getElementById(selectId);
        if (!select) return null;
        return select.closest('.field');
    }

    function addPrefilledHint(selectId) {
        var field = getField(selectId);
        if (!field) return;
        field.classList.add('is-prefilled');
        if (!field.querySelector('.prefilled-hint')) {
            var hint = document.createElement('span');
            hint.className = 'prefilled-hint';
            hint.textContent = 'Подставлено автоматически';
            field.appendChild(hint);
        }
    }

    function removePrefilledHint(selectId) {
        var field = getField(selectId);
        if (!field) return;
        field.classList.remove('is-prefilled');
        var hint = field.querySelector('.prefilled-hint');
        if (hint) hint.remove();
    }

    function updateCards(role) {
        cards.forEach(function (c) {
            c.classList.toggle('is-active', role !== null && c.dataset.role === role);
        });
    }

    var partiesGrid = document.getElementById('parties-grid');
    var forwarderCol = document.getElementById('parties-forwarder-col');

    function syncForwarderCard(role) {
        if (!partiesGrid || !forwarderCol) return;
        var isForwarder = role === 'forwarder';
        forwarderCol.hidden = !isForwarder;
        partiesGrid.classList.toggle('parties-grid--with-forwarder', isForwarder);
    }

    function dispatchRoleChange(role) {
        syncForwarderCard(role);
        document.dispatchEvent(new CustomEvent('trip-role-change', { detail: { role: role } }));
    }

    // ────────────────────────────────────────────────────────────────────
    // Единственный путь обновления UI. Читает состояние формы, вычисляет
    // роль, применяет к DOM.
    //
    //   prefillHintRole — роль, для которой оставить подсветку «подставлено
    //   автоматически». Используется только при ручной активации карточки;
    //   при автодетекте и реакции на пользовательские изменения селектов
    //   должна быть null (без подсказок — пользователь сам выбрал значение).
    // ────────────────────────────────────────────────────────────────────
    function syncFromState(prefillHintRole) {
        var s = readFormState();
        var role = computeTripRole(s.clientId, s.carrierId, s.forwarderId, orgId);
        // observer → null для совместимости с trip_form_finance_role.js:
        // null там означает «показать оба столбца» (как раньше при отсутствии
        // активной роли). Семантически это наблюдатель.
        var uiRole = (role === 'observer') ? null : role;

        updateCards(uiRole);

        Object.keys(ROLE_TO_SELECT).forEach(function (r) {
            if (r === prefillHintRole) {
                addPrefilledHint(ROLE_TO_SELECT[r]);
            } else {
                removePrefilledHint(ROLE_TO_SELECT[r]);
            }
        });

        dispatchRoleChange(uiRole);
    }

    // ── Помощники для программного изменения селекта ──
    function setSelectToOrg(selectId) {
        var select = document.getElementById(selectId);
        if (!select) return;
        if (select.tagName === 'SELECT') {
            var opt = Array.from(select.options).find(function (o) {
                return String(o.value) === String(orgId);
            });
            if (!opt) {
                opt = new Option(orgName, orgId);
                select.add(opt);
            }
        }
        select.value = orgId;
        // autocomplete.js подписан на change: обновит видимый input и кнопку
        // очистки. Наш собственный listener на change защищён _batchDepth,
        // чтобы не вызвать syncFromState посреди батча.
        select.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function clearSelect(selectId) {
        var select = document.getElementById(selectId);
        if (!select) return;
        select.value = '';
        select.dispatchEvent(new Event('change', { bubbles: true }));
    }

    // ────────────────────────────────────────────────────────────────────
    // Батчинг: клик по карточке может менять до двух селектов подряд
    // (снять конкурирующий prefill + выставить целевой). Каждый из них
    // дёрнет change, но мы хотим ровно ОДИН syncFromState в конце — иначе
    // финансовый блок дважды проиграет анимацию смены роли.
    // ────────────────────────────────────────────────────────────────────
    var _batchDepth = 0;
    var _pendingHintRole = null;

    function batch(fn) {
        _batchDepth++;
        try {
            fn();
        } finally {
            _batchDepth--;
            if (_batchDepth === 0) {
                syncFromState(_pendingHintRole);
                _pendingHintRole = null;
            }
        }
    }

    // ── Клик по карточке роли ──
    function activateRoleFromCard(role) {
        batch(function () {
            var s = readFormState();
            var currentRole = computeTripRole(s.clientId, s.carrierId, s.forwarderId, orgId);

            // Повторный клик по активной карточке — снять роль.
            if (currentRole === role) {
                clearSelect(ROLE_TO_SELECT[role]);
                // _pendingHintRole остаётся null → без подсказок.
                return;
            }

            // Освободить другие роли от нашей org (чтобы не было двух
            // подставленных одновременно — это ломает computeTripRole из-за
            // приоритета forwarder > client > carrier и вводит в заблуждение
            // валидаторы same-org).
            Object.keys(ROLE_TO_SELECT).forEach(function (r) {
                if (r === role) return;
                var sel = document.getElementById(ROLE_TO_SELECT[r]);
                if (sel && String(sel.value) === String(orgId)) {
                    clearSelect(ROLE_TO_SELECT[r]);
                }
            });

            setSelectToOrg(ROLE_TO_SELECT[role]);
            _pendingHintRole = role;
        });
    }

    cards.forEach(function (card) {
        card.addEventListener('click', function () {
            activateRoleFromCard(card.dataset.role);
        });
    });

    // ── Реакция на пользовательские изменения селектов участников ──
    //
    // Роль должна быть «липкой» во время редактирования и обновляться
    // только на момент КОММИТА значения:
    //   - выбор из dropdown (selectItem → select.value = id),
    //   - клик по кнопке × (clearBtn → select.value = ''),
    //   - form.reset(),
    //   - blur поля без валидного выбора (ниже отдельный слушатель).
    //
    // autocomplete.js во время набора текста сбрасывает select.value и
    // диспатчит change, если текст перестал совпадать с выбранной опцией.
    // Это ТРАНЗИТНАЯ инвалидация — пользователь ещё печатает. Помечается
    // `select.dataset.acInvalidating='1'` на время диспатча. Такие change
    // игнорируем: иначе финансовый блок флипал бы в «оба столбца» на
    // каждое нажатие backspace в поле «Заказчик».
    Object.keys(ROLE_TO_SELECT).forEach(function (role) {
        var select = document.getElementById(ROLE_TO_SELECT[role]);
        if (!select) return;
        select.addEventListener('change', function () {
            if (_batchDepth > 0) return; // внутри batch — тихо
            if (select.dataset.acInvalidating === '1') return; // транзитная инвалидация
            syncFromState(null);
        });

        // Blur: страховка от edge-case «пользователь набрал мусор и ушёл».
        // autocomplete.js в своём blur-хендлере даёт 200ms на auto-select;
        // если он сработает, change уже обновит UI. Если не сработает —
        // синкнемся сами, чтобы UI отразил финальное (пустое) состояние.
        var container = select.closest('.autocomplete-container');
        var input = container && container.querySelector('.autocomplete-input');
        if (input) {
            input.addEventListener('blur', function () {
                setTimeout(function () {
                    if (_batchDepth > 0) return;
                    syncFromState(null);
                }, 250);
            });
        }
    });

    // ────────────────────────────────────────────────────────────────────
    // Автодетекция при загрузке.
    // - Полностью пустая форма + есть ТС → предзаполнить как carrier
    //   (как и раньше — UX для автопарков).
    // - Иначе — просто пере-вычислить роль из того, что пришло с сервера
    //   (initial в create, instance в update). computeTripRole разрулит.
    // ────────────────────────────────────────────────────────────────────
    var initialState = readFormState();
    var isEmptyForm = !initialState.clientId && !initialState.carrierId && !initialState.forwarderId;
    if (isEmptyForm && hasVehicles) {
        activateRoleFromCard('carrier');
    } else {
        syncFromState(null);
    }
});
