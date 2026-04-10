(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var toggle = document.getElementById('discount-toggle');
        var table  = document.getElementById('lines-table');
        if (!table) return;

        function updateVatColumn() {
            var hasVat = false;
            table.querySelectorAll('[data-line-vat-select]').forEach(function (sel) {
                if (parseInt(sel.value) !== 0) hasVat = true;
            });
            if (hasVat) {
                table.classList.remove('vat-off');
            } else {
                table.classList.add('vat-off');
            }
        }

        table.addEventListener('change', function (e) {
            if (e.target.matches('[data-line-vat-select]')) {
                updateVatColumn();
            }
        });

        if (!toggle) return;

        function applyDiscount(showDiscount) {
            if (showDiscount) {
                table.classList.remove('discount-off');
            } else {
                table.classList.add('discount-off');
                table.querySelectorAll('tr[data-line-row]').forEach(function (row) {
                    var pctEl = row.querySelector('[data-line-disc-pct]');
                    var amtEl = row.querySelector('[data-line-disc-amt]');
                    if (pctEl) pctEl.value = '0.00';
                    if (amtEl) amtEl.value = '0.00';
                    if (window._invoiceLinesRecalcRow) {
                        window._invoiceLinesRecalcRow(row, 'pct');
                    }
                });
            }

            if (window._invoiceLinesUpdateTotals) {
                window._invoiceLinesUpdateTotals();
            }
        }

        applyDiscount(toggle.value === 'on');

        toggle.addEventListener('change', function () {
            applyDiscount(toggle.value === 'on');
        });

        table.addEventListener('click', function (e) {
            var btn = e.target.closest('[data-remove-line]');
            if (!btn) return;
            var row = btn.closest('tr[data-line-row]');
            if (!row) return;

            var rows = table.querySelectorAll('tr[data-line-row]');
            if (rows.length <= 1) return;

            row.remove();
            if (window._invoiceLinesUpdateTotals) {
                window._invoiceLinesUpdateTotals();
            }
        });
    });
})();
