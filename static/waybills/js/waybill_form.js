(function () {
    'use strict';

    /* ── Helpers ── */
    function $(id) { return document.getElementById(id); }
    function val(id) { var el = $(id); return el ? parseFloat(el.value) : NaN; }
    function fmt(n, d) { return n.toLocaleString('ru-RU', { minimumFractionDigits: d, maximumFractionDigits: d }); }

    var rowCounter = 0;

    /* ══════════════════════════════════════════
       Fuel rows — добавление / удаление
    ══════════════════════════════════════════ */
    function addFuelRow(data) {
        var tbody = $('fuel-body');
        if (!tbody) return;

        rowCounter++;
        var id = rowCounter;
        var d = data || {};

        var tr = document.createElement('tr');
        tr.setAttribute('data-row-id', id);
        tr.innerHTML =
            '<td><input type="date" data-field="date" value="' + (d.date || '') + '"></td>' +
            '<td><input type="text" data-field="station" value="' + (d.station || '') + '" placeholder="АЗС..."></td>' +
            '<td><input type="number" data-field="liters" step="0.01" min="0" value="' + (d.liters || '') + '" placeholder="0"></td>' +
            '<td><input type="number" data-field="price_per_liter" step="0.0001" min="0" value="' + (d.price_per_liter || '') + '" placeholder="0.00"></td>' +
            '<td><input type="text" data-field="total_rub" readonly tabindex="-1"></td>' +
            '<td><input type="text" data-field="document_number" value="' + (d.document_number || '') + '" placeholder=""></td>' +
            '<td><button type="button" class="wb-row-delete" title="Удалить">' +
                '<svg width="16" height="16" viewBox="0 0 16 16" fill="none">' +
                '<path d="M2 4h12" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>' +
                '<path d="M13 4v9.5a1.5 1.5 0 0 1-1.5 1.5h-7A1.5 1.5 0 0 1 3 13.5V4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>' +
                '<path d="M5.5 4V2.5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1V4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>' +
                '</svg></button></td>';

        tbody.appendChild(tr);
        calcRowTotal(tr);
        updateFuelBadge();
        recalc();
    }

    function deleteFuelRow(tr) {
        tr.remove();
        updateFuelBadge();
        recalc();
    }

    function calcRowTotal(tr) {
        var liters = parseFloat(tr.querySelector('[data-field="liters"]').value) || 0;
        var price = parseFloat(tr.querySelector('[data-field="price_per_liter"]').value) || 0;
        var totalEl = tr.querySelector('[data-field="total_rub"]');
        if (liters > 0 && price > 0) {
            totalEl.value = fmt(liters * price, 2);
        } else {
            totalEl.value = '';
        }
    }

    function updateFuelBadge() {
        var badge = $('fuel-count-badge');
        if (!badge) return;
        var rows = document.querySelectorAll('#fuel-body tr');
        var n = rows.length;
        var word = 'заправок';
        if (n === 1) word = 'заправка';
        else if (n >= 2 && n <= 4) word = 'заправки';
        badge.textContent = n + ' ' + word;
    }

    /* ══════════════════════════════════════════
       syncHidden — сериализация в JSON
    ══════════════════════════════════════════ */
    function syncHidden() {
        var rows = document.querySelectorAll('#fuel-body tr');
        var entries = [];
        rows.forEach(function (tr) {
            var entry = {};
            tr.querySelectorAll('input[data-field]').forEach(function (inp) {
                if (inp.getAttribute('data-field') !== 'total_rub') {
                    entry[inp.getAttribute('data-field')] = inp.value;
                }
            });
            if (entry.liters) entries.push(entry);
        });
        var hidden = $('fuel-entries-json');
        if (hidden) hidden.value = JSON.stringify(entries);
    }

    /* ══════════════════════════════════════════
       Derived metrics (пробег, время, скорость)
    ══════════════════════════════════════════ */
    function calcDerived() {
        var startOdo = val('start-odometer');
        var endOdo = val('end-odometer');
        var mileageEl = $('metric-mileage');
        var durationEl = $('metric-duration');
        var speedEl = $('metric-speed');
        var mileage = null;
        var durationHours = null;

        // Пробег
        if (!isNaN(startOdo) && !isNaN(endOdo) && endOdo > startOdo) {
            mileage = endOdo - startOdo;
            mileageEl.textContent = fmt(mileage, 0) + ' км';
            mileageEl.classList.remove('wb-metric-value--placeholder');
        } else {
            mileageEl.textContent = '—';
            mileageEl.classList.add('wb-metric-value--placeholder');
        }

        // Время
        var startDt = $('start-dt') ? $('start-dt').value : '';
        var endDt = $('end-dt') ? $('end-dt').value : '';
        if (startDt && endDt) {
            var ms = new Date(endDt) - new Date(startDt);
            if (ms > 0) {
                durationHours = ms / 3600000;
                var h = Math.floor(durationHours);
                var m = Math.round((durationHours - h) * 60);
                durationEl.textContent = h + ' ч ' + (m < 10 ? '0' : '') + m + ' мин';
                durationEl.classList.remove('wb-metric-value--placeholder');
            } else {
                durationEl.textContent = '—';
                durationEl.classList.add('wb-metric-value--placeholder');
            }
        } else {
            durationEl.textContent = '—';
            durationEl.classList.add('wb-metric-value--placeholder');
        }

        // Скорость
        if (mileage !== null && durationHours !== null && durationHours > 0) {
            speedEl.textContent = fmt(mileage / durationHours, 0) + ' км/ч';
            speedEl.classList.remove('wb-metric-value--placeholder');
        } else {
            speedEl.textContent = '—';
            speedEl.classList.add('wb-metric-value--placeholder');
        }

        // Валидация: подсветка ошибок
        var startOdoEl = $('start-odometer');
        var endOdoEl = $('end-odometer');
        if (startOdoEl && endOdoEl && !isNaN(startOdo) && !isNaN(endOdo) && endOdo <= startOdo) {
            endOdoEl.classList.add('is-invalid');
        } else if (endOdoEl) {
            endOdoEl.classList.remove('is-invalid');
        }

        var startDtEl = $('start-dt');
        var endDtEl = $('end-dt');
        if (startDtEl && endDtEl && startDt && endDt && new Date(endDt) <= new Date(startDt)) {
            endDtEl.classList.add('is-invalid');
        } else if (endDtEl) {
            endDtEl.classList.remove('is-invalid');
        }

        return { mileage: mileage, durationHours: durationHours };
    }

    /* ══════════════════════════════════════════
       Analytics (аналитика расхода)
    ══════════════════════════════════════════ */
    function calcAnalytics(mileage) {
        var block = $('analytics-block');
        if (!block) return;

        var startFuel = val('start-fuel');
        var endFuel = val('end-fuel');
        var fuelNorm = val('fuel-norm');

        // Сумма заправок
        var totalLiters = 0;
        var totalRub = 0;
        var rows = document.querySelectorAll('#fuel-body tr');
        rows.forEach(function (tr) {
            var l = parseFloat(tr.querySelector('[data-field="liters"]').value) || 0;
            var p = parseFloat(tr.querySelector('[data-field="price_per_liter"]').value) || 0;
            totalLiters += l;
            if (l > 0 && p > 0) totalRub += l * p;
        });

        // Показываем итого заправок
        $('fuel-total-liters').textContent = fmt(totalLiters, 1) + ' л';
        $('fuel-total-rub').textContent = totalRub > 0 ? fmt(totalRub, 2) + ' \u20bd' : '0 \u20bd';

        var hasData = (!isNaN(startFuel) || !isNaN(endFuel) || totalLiters > 0 || (!isNaN(fuelNorm) && mileage));
        if (!hasData) {
            block.hidden = true;
            return;
        }
        block.hidden = false;

        // Израсходовано = начало + заправки - конец
        var consumed = null;
        if (!isNaN(startFuel) && !isNaN(endFuel)) {
            consumed = startFuel + totalLiters - endFuel;
            $('an-consumed').textContent = fmt(consumed, 1) + ' л';
        } else {
            $('an-consumed').textContent = '—';
        }

        // Норматив
        var normTotal = null;
        if (!isNaN(fuelNorm) && mileage) {
            normTotal = fuelNorm * mileage / 100;
            $('an-norm').textContent = fmt(normTotal, 1) + ' л';
            $('an-norm-hint').textContent = fuelNorm + ' \u00d7 ' + mileage + ' км / 100';
        } else {
            $('an-norm').textContent = '—';
            $('an-norm-hint').textContent = '';
        }

        // Отклонение
        var devEl = $('an-deviation');
        var devHint = $('an-deviation-hint');
        if (consumed !== null && normTotal !== null) {
            var dev = consumed - normTotal;
            var avgPrice = totalLiters > 0 && totalRub > 0 ? totalRub / totalLiters : 0;
            var devRub = Math.abs(dev) * avgPrice;

            devEl.textContent = (dev > 0 ? '+' : '') + fmt(dev, 1) + ' л';
            devEl.className = 'wb-analytics-cell-value';

            if (dev > 0.5) {
                devEl.classList.add('wb-analytics-cell-value--negative');
                devHint.textContent = avgPrice > 0 ? fmt(devRub, 2) + ' \u20bd сверх нормы' : '';
            } else if (dev < -0.5) {
                devEl.classList.add('wb-analytics-cell-value--positive');
                devHint.textContent = avgPrice > 0 ? fmt(devRub, 2) + ' \u20bd экономия' : '';
            } else {
                devHint.textContent = 'в пределах нормы';
            }
        } else {
            devEl.textContent = '—';
            devEl.className = 'wb-analytics-cell-value';
            devHint.textContent = '';
        }

        // Факт. расход
        if (consumed !== null && mileage && mileage > 0) {
            $('an-actual-rate').textContent = fmt(consumed / mileage * 100, 1);
        } else {
            $('an-actual-rate').textContent = '—';
        }

        // Progress bar
        var progressWrap = $('progress-wrap');
        if (consumed !== null && normTotal !== null && normTotal > 0) {
            progressWrap.hidden = false;
            var maxVal = Math.max(consumed, normTotal) * 1.12;
            var factPct = Math.min(consumed / maxVal * 100, 100);
            var normPct = normTotal / maxVal * 100;

            var fill = $('progress-fill');
            fill.style.width = factPct + '%';
            fill.className = 'wb-progress-fill ' + (consumed > normTotal ? 'wb-progress-fill--over' : 'wb-progress-fill--ok');

            $('progress-norm-line').style.left = normPct + '%';
            $('progress-fact-label').textContent = fmt(consumed, 1) + ' л';
            $('progress-norm-label').textContent = fmt(normTotal, 1) + ' л';
        } else {
            progressWrap.hidden = true;
        }
    }

    /* ══════════════════════════════════════════
       Summary bar (итоговая строка)
    ══════════════════════════════════════════ */
    function calcSummaryBar(mileage) {
        var sumMileage = $('sum-mileage');
        var sumFuel = $('sum-fuel');
        var sumOther = $('sum-other');
        var sumTotal = $('sum-total');

        // Пробег
        if (mileage) {
            sumMileage.textContent = fmt(mileage, 0) + ' км';
            sumMileage.classList.remove('wb-summary-value--placeholder');
        } else {
            sumMileage.textContent = '—';
            sumMileage.classList.add('wb-summary-value--placeholder');
        }

        // Топливо (сумма руб)
        var fuelRub = 0;
        document.querySelectorAll('#fuel-body tr').forEach(function (tr) {
            var l = parseFloat(tr.querySelector('[data-field="liters"]').value) || 0;
            var p = parseFloat(tr.querySelector('[data-field="price_per_liter"]').value) || 0;
            if (l > 0 && p > 0) fuelRub += l * p;
        });

        if (fuelRub > 0) {
            sumFuel.textContent = fmt(fuelRub, 2) + ' \u20bd';
            sumFuel.classList.remove('wb-summary-value--placeholder');
        } else {
            sumFuel.textContent = '—';
            sumFuel.classList.add('wb-summary-value--placeholder');
        }

        // Прочие расходы
        var otherCosts = 0;
        document.querySelectorAll('.cost-field').forEach(function (inp) {
            otherCosts += parseFloat(inp.value) || 0;
        });

        if (otherCosts > 0) {
            sumOther.textContent = fmt(otherCosts, 2) + ' \u20bd';
            sumOther.classList.remove('wb-summary-value--placeholder');
        } else {
            sumOther.textContent = '—';
            sumOther.classList.add('wb-summary-value--placeholder');
        }

        // Итого
        var total = fuelRub + otherCosts;
        if (total > 0) {
            sumTotal.textContent = fmt(total, 2) + ' \u20bd';
            sumTotal.classList.remove('wb-summary-value--placeholder');
        } else {
            sumTotal.textContent = '—';
            sumTotal.classList.add('wb-summary-value--placeholder');
        }
    }

    /* ══════════════════════════════════════════
       Topbar update
    ══════════════════════════════════════════ */
    function updateTopbar() {
        var series = $('wb-series') ? $('wb-series').value.trim() : '';
        var number = $('wb-number') ? $('wb-number').value.trim() : '';
        var title = $('topbar-title');

        if (series || number) {
            title.textContent = 'ПЛ № ' + (series || '—') + ' / ' + (number || '—');
        } else {
            title.textContent = 'ПЛ № —';
        }

        var parts = [];
        var issueDate = $('wb-issue-date') ? $('wb-issue-date').value : '';
        if (issueDate) {
            var d = new Date(issueDate);
            parts.push(d.toLocaleDateString('ru-RU'));
        }
        var driver = $('wb-driver') ? $('wb-driver').value.trim() : '';
        if (driver) parts.push(driver);
        var vehicle = $('wb-vehicle') ? $('wb-vehicle').value.trim() : '';
        if (vehicle) parts.push(vehicle);

        $('topbar-subtitle').textContent = parts.join(' \u00b7 ');
    }

    /* ══════════════════════════════════════════
       Central recalc
    ══════════════════════════════════════════ */
    function recalc() {
        var derived = calcDerived();
        calcAnalytics(derived.mileage);
        calcSummaryBar(derived.mileage);
        syncHidden();
        updateTopbar();
    }

    /* ══════════════════════════════════════════
       Event binding
    ══════════════════════════════════════════ */
    document.addEventListener('DOMContentLoaded', function () {
        // Основные поля → recalc
        ['start-odometer', 'end-odometer', 'start-dt', 'end-dt',
         'start-fuel', 'end-fuel', 'fuel-norm',
         'wb-series', 'wb-number', 'wb-issue-date', 'wb-driver', 'wb-vehicle'
        ].forEach(function (id) {
            var el = $(id);
            if (el) {
                el.addEventListener('input', recalc);
                el.addEventListener('change', recalc);
            }
        });

        // Прочие расходы
        document.querySelectorAll('.cost-field').forEach(function (inp) {
            inp.addEventListener('input', recalc);
        });

        // Делегирование событий в таблице заправок
        var fuelBody = $('fuel-body');
        if (fuelBody) {
            fuelBody.addEventListener('input', function (e) {
                var tr = e.target.closest('tr');
                if (tr) {
                    calcRowTotal(tr);
                    recalc();
                }
            });
            fuelBody.addEventListener('click', function (e) {
                var btn = e.target.closest('.wb-row-delete');
                if (btn) {
                    var tr = btn.closest('tr');
                    if (tr) deleteFuelRow(tr);
                }
            });
        }

        // Кнопка добавления заправки
        var addBtn = $('add-fuel-btn');
        if (addBtn) {
            addBtn.addEventListener('click', function () {
                addFuelRow();
            });
        }

        // Submit — синхронизировать hidden
        var form = $('wb-form');
        if (form) {
            form.addEventListener('submit', function () {
                syncHidden();
            });
        }

        // Начальное состояние
        recalc();
    });
})();
