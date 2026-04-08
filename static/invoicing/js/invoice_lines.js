(function () {
    'use strict';

    function parseNum(str) {
        if (str === null || str === undefined) return 0;
        return parseFloat(String(str).replace(',', '.').replace(/\s/g, '')) || 0;
    }

    function sanitizeDecimal(input) {
        var pos = input.selectionStart;
        var val = input.value.replace(',', '.');
        val = val.replace(/[^0-9.]/g, '');
        var parts = val.split('.');
        if (parts.length > 2) {
            val = parts[0] + '.' + parts.slice(1).join('');
        }
        if (input.value !== val) {
            var newPos = Math.max(0, pos - (input.value.length - val.length));
            input.value = val;
            input.setSelectionRange(newPos, newPos);
        }
    }

    function round2(n) {
        return Math.round(n * 100) / 100;
    }

    function fmt(n) {
        return round2(n).toFixed(2);
    }

    function fmtMoney(n) {
        var fixed = round2(n).toFixed(2);
        var parts = fixed.split('.');
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '\u00A0');
        return parts.join('.');
    }

    function recalcRow(row, source) {
        var priceEl   = row.querySelector('[data-line-price]');
        var pctEl     = row.querySelector('[data-line-disc-pct]');
        var amtEl     = row.querySelector('[data-line-disc-amt]');
        var vatEl     = row.querySelector('[data-line-vat-select]');
        var netCell   = row.querySelector('[data-line-net]');
        var vatCell   = row.querySelector('[data-line-vat]');
        var totalCell = row.querySelector('[data-line-total]');

        var price   = parseNum(priceEl && priceEl.value);
        var vatRate = vatEl ? (parseInt(vatEl.value) || 0) : 0;

        var maxAmt = Math.max(0, round2(price - 0.01));
        var pct, discAmt;

        if (source === 'amt' && amtEl) {
            discAmt = parseNum(amtEl.value);
            if (discAmt > maxAmt) { discAmt = maxAmt; amtEl.value = fmt(discAmt); }
            pct = price > 0 ? round2(discAmt / price * 100) : 0;
            if (pctEl) pctEl.value = fmt(pct);
        } else {
            pct = parseNum(pctEl && pctEl.value);
            if (pct > 99.99) { pct = 99.99; if (pctEl) pctEl.value = fmt(pct); }
            discAmt = round2(price * pct / 100);
            if (amtEl) amtEl.value = fmt(discAmt);
        }

        var net   = round2(price - discAmt);
        var vat   = round2(net * vatRate / 100);
        var total = round2(net + vat);

        if (netCell)   netCell.textContent   = fmtMoney(net);
        if (vatCell)   vatCell.textContent   = fmtMoney(vat);
        if (totalCell) totalCell.textContent = fmtMoney(total);

        updateTotals();
    }

    function updateTotals() {
        var table = document.querySelector('.lines-table');
        if (!table) return;

        var sumNet = 0, sumVat = 0, sumTotal = 0;
        table.querySelectorAll('tr[data-line-row]').forEach(function (row) {
            sumNet   += parseNum(row.querySelector('[data-line-net]') && row.querySelector('[data-line-net]').textContent);
            sumVat   += parseNum(row.querySelector('[data-line-vat]') && row.querySelector('[data-line-vat]').textContent);
            sumTotal += parseNum(row.querySelector('[data-line-total]') && row.querySelector('[data-line-total]').textContent);
        });

        var footNet   = table.querySelector('[data-foot-net]');
        var footVat   = table.querySelector('[data-foot-vat]');
        var footTotal = table.querySelector('[data-foot-total]');
        if (footNet)   footNet.textContent   = fmtMoney(sumNet);
        if (footVat)   footVat.textContent   = fmtMoney(sumVat);
        if (footTotal) footTotal.textContent = fmtMoney(sumTotal);

    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('tr[data-line-row]').forEach(function (row) {
            var priceEl = row.querySelector('[data-line-price]');
            var pctEl   = row.querySelector('[data-line-disc-pct]');
            var amtEl   = row.querySelector('[data-line-disc-amt]');
            var vatEl   = row.querySelector('[data-line-vat-select]');

            ['[data-line-net]', '[data-line-vat]', '[data-line-total]'].forEach(function (sel) {
                var cell = row.querySelector(sel);
                if (cell) cell.textContent = fmtMoney(parseNum(cell.textContent));
            });

            if (priceEl) priceEl.addEventListener('input', function () { sanitizeDecimal(priceEl); recalcRow(row, 'pct'); });
            if (pctEl)   pctEl.addEventListener('input',   function () { sanitizeDecimal(pctEl);   recalcRow(row, 'pct'); });
            if (amtEl)   amtEl.addEventListener('input',   function () { sanitizeDecimal(amtEl);   recalcRow(row, 'amt'); });
            if (vatEl)   vatEl.addEventListener('change',  function () { recalcRow(row, 'pct'); });
        });

        updateTotals();
    });
})();
