(function () {
    'use strict';

    function initVatToggle(methodId, vatWrapId) {
        var method = document.getElementById(methodId);
        var wrap = document.getElementById(vatWrapId);
        if (!method || !wrap) return;
        var vatSelect = wrap.querySelector('select');
        function update() {
            var show = method.value === 'cashless';
            wrap.style.display = show ? '' : 'none';
            if (!show && vatSelect) vatSelect.value = '';
        }
        method.addEventListener('change', update);
        update();
    }

    function initTermToggle(radioName, termInputId) {
        var radios = document.querySelectorAll('input[name="' + radioName + '"]');
        var termInput = document.getElementById(termInputId);
        if (!radios.length || !termInput) return;
        function update() {
            var isUnloading = false;
            radios.forEach(function (r) { if (r.checked && r.value === 'unloading') isUnloading = true; });
            termInput.disabled = isUnloading;
            termInput.style.opacity = isUnloading ? '0.35' : '';
        }
        radios.forEach(function (r) { r.addEventListener('change', update); });
        update();
    }

    function initQuantityTotal(opts) {
        var unitSel   = document.getElementById(opts.unitId);
        var costInput = document.getElementById(opts.costId);
        var qtyRow    = document.getElementById(opts.qtyRowId);
        var qtyBadge  = document.getElementById(opts.qtyBadgeId);
        var qtyInput  = document.getElementById(opts.qtyInputId);
        var totalHint = document.getElementById(opts.totalHintId);
        var totalVal  = document.getElementById(opts.totalValueId);
        var weightEl  = document.getElementById(opts.weightId);
        var volumeEl  = document.getElementById(opts.volumeId);
        if (!unitSel || !costInput) return;

        var UNIT_LABELS = { rub_km: 'км', rub_hour: 'ч' };
        var UNIT_CARGO  = { rub_kg: 'кг', rub_cbm: 'м³' };

        function formatNum(n) {
            return n.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }

        function getQty(unit) {
            if (unit === 'rub_kg')   return weightEl ? parseFloat(weightEl.value) || null : null;
            if (unit === 'rub_cbm')  return volumeEl ? parseFloat(volumeEl.value) || null : null;
            if (unit === 'rub_km' || unit === 'rub_hour')
                return qtyInput ? parseFloat(qtyInput.value) || null : null;
            return null;
        }

        function update() {
            var unit = unitSel.value;
            var cost = parseFloat(costInput.value) || null;

            if (qtyRow) {
                var needQtyInput = unit === 'rub_km' || unit === 'rub_hour';
                qtyRow.style.display = needQtyInput ? '' : 'none';
                if (qtyBadge) qtyBadge.textContent = UNIT_LABELS[unit] || '';
            }

            if (!totalHint || !totalVal) return;
            if (unit === 'rub') {
                if (cost !== null) {
                    totalHint.style.display = '';
                    totalVal.textContent = formatNum(cost) + ' \u20bd';
                } else {
                    totalHint.style.display = 'none';
                }
                return;
            }
            var qty = getQty(unit);
            var unitLabel = UNIT_LABELS[unit] || UNIT_CARGO[unit] || '';
            if (cost !== null && qty !== null) {
                totalHint.style.display = '';
                totalVal.textContent = formatNum(cost * qty) + ' \u20bd'
                    + ' (' + cost + ' \u00d7 ' + qty + '\u00a0' + unitLabel + ')';
            } else {
                totalHint.style.display = 'none';
            }
        }

        unitSel.addEventListener('change', update);
        costInput.addEventListener('input', update);
        if (qtyInput)  qtyInput.addEventListener('input', update);
        if (weightEl)  weightEl.addEventListener('input', update);
        if (volumeEl)  volumeEl.addEventListener('input', update);
        update();
    }

    document.addEventListener('DOMContentLoaded', function () {
        initVatToggle('id_client_payment_method', 'client-vat-wrap');
        initVatToggle('id_carrier_payment_method', 'carrier-vat-wrap');
        initTermToggle('payment_condition', 'id_payment_term');
        initTermToggle('carrier_payment_condition', 'id_carrier_payment_term');

        initQuantityTotal({
            unitId:      'id_client_cost_unit',
            costId:      'id_client_cost',
            qtyRowId:    'client-qty-row',
            qtyBadgeId:  'client-qty-badge',
            qtyInputId:  'id_client_quantity',
            totalHintId: 'client-total-hint',
            totalValueId:'client-total-value',
            weightId:    'id_weight',
            volumeId:    'id_volume',
        });
        initQuantityTotal({
            unitId:      'id_carrier_cost_unit',
            costId:      'id_carrier_cost',
            qtyRowId:    'carrier-qty-row',
            qtyBadgeId:  'carrier-qty-badge',
            qtyInputId:  'id_carrier_quantity',
            totalHintId: 'carrier-total-hint',
            totalValueId:'carrier-total-value',
            weightId:    'id_weight',
            volumeId:    'id_volume',
        });
    });
})();
