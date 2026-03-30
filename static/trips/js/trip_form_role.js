document.addEventListener('DOMContentLoaded', function () {
    var config = document.getElementById('role-config');
    if (!config) return;

    var orgId = config.dataset.orgId;
    var orgName = config.dataset.orgName;
    var hasVehicles = config.dataset.hasVehicles === 'true';

    var cards = document.querySelectorAll('.role-card');
    var ROLE_TO_SELECT = {
        client: 'id_client',
        carrier: 'id_carrier',
    };

    var activeRole = null;

    function getField(selectId) {
        var select = document.getElementById(selectId);
        if (!select) return null;
        return select.closest('.field');
    }

    function setSelectValue(selectId) {
        var select = document.getElementById(selectId);
        if (!select) return;

        var opt = Array.from(select.options).find(function (o) {
            return String(o.value) === String(orgId);
        });
        if (!opt) {
            opt = new Option(orgName, orgId);
            select.add(opt);
        }
        select.value = orgId;
        select.dispatchEvent(new Event('change', { bubbles: true }));

        var field = select.closest('.field');
        if (field) {
            field.classList.add('is-prefilled');
            if (!field.querySelector('.prefilled-hint')) {
                var hint = document.createElement('span');
                hint.className = 'prefilled-hint';
                hint.textContent = 'Подставлено автоматически';
                field.appendChild(hint);
            }
        }
    }

    function clearSelectValue(selectId) {
        var select = document.getElementById(selectId);
        if (!select) return;

        select.value = '';
        select.dispatchEvent(new Event('change', { bubbles: true }));

        var field = select.closest('.field');
        if (field) {
            removePrefilled(field);
        }
    }

    function removePrefilled(field) {
        field.classList.remove('is-prefilled');
        var hint = field.querySelector('.prefilled-hint');
        if (hint) hint.remove();
    }

    function activateRole(role) {
        // Очистить предыдущее подставленное значение
        if (activeRole && ROLE_TO_SELECT[activeRole]) {
            clearSelectValue(ROLE_TO_SELECT[activeRole]);
        }

        // Снять is-active со всех карточек
        cards.forEach(function (c) { c.classList.remove('is-active'); });

        // Повторный клик — снять выбор
        if (activeRole === role) {
            activeRole = null;
            return;
        }

        activeRole = role;

        // Поставить is-active на выбранную
        var card = document.querySelector('.role-card[data-role="' + role + '"]');
        if (card) card.classList.add('is-active');

        // Подставить организацию в нужный select
        var selectId = ROLE_TO_SELECT[role];
        if (selectId) {
            setSelectValue(selectId);
        }
    }

    // Клик по карточкам
    cards.forEach(function (card) {
        card.addEventListener('click', function () {
            activateRole(card.dataset.role);
        });
    });

    function deactivateRole(role) {
        cards.forEach(function (c) { c.classList.remove('is-active'); });
        var selectId = ROLE_TO_SELECT[role];
        if (selectId) {
            var field = getField(selectId);
            if (field) removePrefilled(field);
        }
        activeRole = null;
    }

    // Любое изменение подставленного поля — сбросить карточку роли
    Object.keys(ROLE_TO_SELECT).forEach(function (role) {
        var selectId = ROLE_TO_SELECT[role];
        var select = document.getElementById(selectId);
        if (!select) return;

        // Смена значения в select (крестик, выбор из дропдауна)
        select.addEventListener('change', function () {
            if (activeRole === role) {
                // Карточка активна — деактивировать при любом другом значении
                if (String(select.value) !== String(orgId)) {
                    deactivateRole(role);
                }
            } else {
                // Карточка не активна — подсветить если выбрана своя организация
                if (String(select.value) === String(orgId)) {
                    cards.forEach(function (c) { c.classList.remove('is-active'); });
                    if (activeRole && ROLE_TO_SELECT[activeRole]) {
                        var prevField = getField(ROLE_TO_SELECT[activeRole]);
                        if (prevField) removePrefilled(prevField);
                    }
                    activeRole = role;
                    var card = document.querySelector('.role-card[data-role="' + role + '"]');
                    if (card) card.classList.add('is-active');
                }
            }
        });

        // Ввод текста в видимый input автокомплита
        var acInput = select.closest('.autocomplete-container');
        acInput = acInput && acInput.querySelector('.autocomplete-input');
        if (acInput) {
            acInput.addEventListener('input', function () {
                if (activeRole !== role) return;
                deactivateRole(role);
            });
        }
    });

    // Автодетекция при загрузке
    var clientSelect = document.getElementById('id_client');
    var carrierSelect = document.getElementById('id_carrier');
    var clientIsOrg = clientSelect && String(clientSelect.value) === String(orgId);
    var carrierIsOrg = carrierSelect && String(carrierSelect.value) === String(orgId);
    var formHasValues = (clientSelect && clientSelect.value) || (carrierSelect && carrierSelect.value);

    if (clientIsOrg) {
        // Своя org в поле «Заказчик» — подсветить карточку без prefilled
        activeRole = 'client';
        var card = document.querySelector('.role-card[data-role="client"]');
        if (card) card.classList.add('is-active');
    } else if (carrierIsOrg) {
        // Своя org в поле «Перевозчик» — подсветить карточку без prefilled
        activeRole = 'carrier';
        var card = document.querySelector('.role-card[data-role="carrier"]');
        if (card) card.classList.add('is-active');
    } else if (hasVehicles && !formHasValues) {
        // Пустая форма — автоподстановка
        activateRole('carrier');
    }
});
