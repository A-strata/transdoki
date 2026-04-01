(function () {
    'use strict';

    var clientCol = document.getElementById('finance-client-col');
    var carrierCol = document.getElementById('finance-carrier-col');
    var clientTitle = document.getElementById('finance-client-title');
    var carrierTitle = document.getElementById('finance-carrier-title');
    var clientHint = document.getElementById('finance-client-hint');
    var carrierHint = document.getElementById('finance-carrier-hint');
    var marginBlock = document.getElementById('margin-block');
    var marginValue = document.getElementById('margin-value');
    var marginPercent = document.getElementById('margin-percent');

    if (!clientCol || !carrierCol) return;

    var clientCostInput = document.getElementById('id_client_cost');
    var carrierCostInput = document.getElementById('id_carrier_cost');

    function formatNum(n) {
        return n.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    }

    function updateMargin() {
        if (!marginBlock || marginBlock.hidden) return;
        var income = parseFloat(clientCostInput ? clientCostInput.value : '') || 0;
        var expense = parseFloat(carrierCostInput ? carrierCostInput.value : '') || 0;

        if (!income && !expense) {
            marginValue.textContent = '— ₽';
            marginPercent.textContent = '';
            marginPercent.className = 'margin-block-percent';
            return;
        }

        var diff = income - expense;
        marginValue.textContent = formatNum(diff) + ' ₽';

        if (income > 0) {
            var pct = Math.round(diff / income * 100);
            marginPercent.textContent = pct + '%';
            marginPercent.className = 'margin-block-percent ' + (pct >= 0 ? 'is-positive' : 'is-negative');
        } else {
            marginPercent.textContent = '';
            marginPercent.className = 'margin-block-percent';
        }
    }

    function applyRole(role) {
        // Сброс к дефолту
        clientCol.style.display = '';
        carrierCol.style.display = '';
        clientCol.classList.remove('finance-col--income', 'finance-col--expense');
        carrierCol.classList.remove('finance-col--income', 'finance-col--expense');
        clientTitle.textContent = 'Ставка заказчику';
        carrierTitle.textContent = 'Ставка перевозчику';
        if (clientHint) { clientHint.hidden = true; clientHint.textContent = ''; }
        if (carrierHint) { carrierHint.hidden = true; carrierHint.textContent = ''; }
        if (marginBlock) marginBlock.hidden = true;

        if (role === 'client') {
            // Заказчик: скрыть левый, оставить правый
            clientCol.style.display = 'none';
            carrierTitle.textContent = 'Стоимость перевозки';
            if (carrierHint) {
                carrierHint.textContent = 'Сумма, которую вы заплатите за перевозку';
                carrierHint.hidden = false;
            }
        } else if (role === 'carrier') {
            // Перевозчик: скрыть правый, оставить левый
            carrierCol.style.display = 'none';
            clientTitle.textContent = 'Стоимость перевозки';
            if (clientHint) {
                clientHint.textContent = 'Сумма, которую вы получите за перевозку';
                clientHint.hidden = false;
            }
        } else if (role === 'forwarder') {
            // Экспедитор: оба столбца + акценты + маржа
            clientTitle.textContent = 'Заказчик платит нам';
            carrierTitle.textContent = 'Мы платим перевозчику';
            clientCol.classList.add('finance-col--income');
            carrierCol.classList.add('finance-col--expense');
            if (marginBlock) {
                marginBlock.hidden = false;
                updateMargin();
            }
        }
    }

    // Анимация при смене роли
    function animateBlocks() {
        var targets = [
            document.getElementById('section-participants'),
            document.getElementById('section-finance')
        ];
        targets.forEach(function (el) {
            if (!el) return;
            el.classList.remove('role-animate');
            // Force reflow to restart animation
            void el.offsetWidth;
            el.classList.add('role-animate');
        });
    }

    // Слушаем событие смены роли
    document.addEventListener('trip-role-change', function (e) {
        applyRole(e.detail.role);
        animateBlocks();
    });

    // Пересчёт маржи при вводе ставок
    if (clientCostInput) clientCostInput.addEventListener('input', updateMargin);
    if (carrierCostInput) carrierCostInput.addEventListener('input', updateMargin);
})();
