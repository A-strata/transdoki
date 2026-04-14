(function () {
    'use strict';

    // ─── Утилиты ──────────────────────────────────────────────────────────

    // Принимает строку "1 234,56" или "1234.56" → число с плавающей точкой
    function parseNum(str) {
        if (str === null || str === undefined) return 0;
        var s = String(str).trim().replace(/\s/g, '').replace(',', '.');
        var n = parseFloat(s);
        return isNaN(n) ? 0 : n;
    }

    // Форматирует число в "1 234,56" (неразрывный пробел как разделитель тысяч)
    function formatMoney(n) {
        var fixed = n.toFixed(2);
        var parts = fixed.split('.');
        var integer = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0');
        return integer + ',' + parts[1];
    }

    // ─── Пересчёт одной строки ────────────────────────────────────────────
    // Считает net, vat, total по значениям полей строки и записывает
    // результат в ячейки data-line-vat и data-line-total.
    // Возвращает объект {net, vat, total} для суммирования в итогах.

    function calcRow(row) {
        var qty       = parseNum(row.querySelector('[data-line-qty]')     && row.querySelector('[data-line-qty]').value);
        var price     = parseNum(row.querySelector('[data-line-price]')   && row.querySelector('[data-line-price]').value);
        var discPct   = parseNum(row.querySelector('[data-line-disc-pct]') && row.querySelector('[data-line-disc-pct]').value);
        var discAmtEl = row.querySelector('[data-line-disc-amt]');
        var vatSel    = row.querySelector('[data-line-vat-select]');
        var netCell   = row.querySelector('[data-line-net]');
        var vatCell   = row.querySelector('[data-line-vat]');
        var totalCell = row.querySelector('[data-line-total]');

        if (!vatCell || !totalCell) return { net: 0, vat: 0, total: 0 };

        // Сумма до скидки: qty × price
        var gross = Math.round(qty * price * 100) / 100;

        // Скидка: приоритет за процентом — если процент задан, пересчитываем
        // поле суммы скидки; иначе берём сумму напрямую
        var discAmt = 0;
        if (discPct > 0) {
            discAmt = Math.round(gross * discPct / 100 * 100) / 100;
            if (discAmtEl) discAmtEl.value = formatMoney(discAmt);
        } else if (discAmtEl) {
            discAmt = parseNum(discAmtEl.value);
        }
        if (discAmt > gross) discAmt = gross;

        var net = Math.round((gross - discAmt) * 100) / 100;

        // НДС: если ставка не выбрана (пустой option "Без НДС") — НДС = 0
        var vatRate = vatSel ? parseInt(vatSel.value, 10) : NaN;
        var vat = 0;
        if (!isNaN(vatRate) && vatSel && vatSel.value !== '') {
            vat = Math.round(net * vatRate / 100 * 100) / 100;
        }

        var total = Math.round((net + vat) * 100) / 100;

        // Без НДС → прочерк в ячейке, чтобы не путать с нулевой ставкой 0%
        var hasRate = vatSel && vatSel.value !== '';
        if (netCell) netCell.textContent = formatMoney(net);
        vatCell.textContent   = hasRate ? formatMoney(vat) : '—';
        totalCell.textContent = formatMoney(total);

        return { net: net, vat: vat, total: total };
    }

    // ─── Обновление итогов под таблицей ───────────────────────────────────
    // Суммирует все видимые строки, обновляет data-foot-* и управляет
    // видимостью колонки НДС (класс vat-off на таблице).

    function updateTotals(table) {
        var rows = table.querySelectorAll('[data-line-row]');
        var sumNet = 0, sumVat = 0, sumTotal = 0;
        var hasVat = false;

        rows.forEach(function (row) {
            // Строки помеченные DELETE не учитываются в итогах
            var delChk = row.querySelector('input[name$="-DELETE"]');
            if (delChk && delChk.checked) return;

            var r = calcRow(row);
            sumNet   += r.net;
            sumVat   += r.vat;
            sumTotal += r.total;

            var vatSel = row.querySelector('[data-line-vat-select]');
            if (vatSel && vatSel.value !== '') hasVat = true;
        });

        // Колонка «Сумма НДС» теперь всегда видна — не переключаем класс vat-off.
        // В строках без ставки отображается прочерк (см. calcRow).

        // Обновляем строки итогов внизу секции
        var footNet   = document.querySelector('[data-foot-net]');
        var footVat   = document.querySelector('[data-foot-vat]');
        var footLabel = document.querySelector('[data-foot-vat-label]');
        var footTotal = document.querySelector('[data-foot-total]');

        if (footNet)   footNet.textContent   = formatMoney(Math.round(sumNet   * 100) / 100);
        if (footVat)   footVat.textContent   = hasVat ? formatMoney(Math.round(sumVat   * 100) / 100) : '—';
        if (footTotal) footTotal.textContent = formatMoney(Math.round(sumTotal * 100) / 100);

        // Подпись строки НДС: конкретная ставка, "смеш." или "Не облагается"
        if (footLabel) {
            if (hasVat) {
                var rates = new Set();
                rows.forEach(function (row) {
                    var delChk = row.querySelector('input[name$="-DELETE"]');
                    if (delChk && delChk.checked) return;
                    var vatSel = row.querySelector('[data-line-vat-select]');
                    if (vatSel && vatSel.value !== '') rates.add(vatSel.value);
                });
                footLabel.textContent = rates.size === 1
                    ? 'НДС ' + rates.values().next().value + '%'
                    : 'НДС (смеш.)';
            } else {
                footLabel.textContent = 'Не облагается НДС';
            }
        }
    }

    // ─── Подписка на события строки ───────────────────────────────────────
    // Вешает обработчики input/change на все поля строки, а также
    // отслеживает удаление строки через чекбокс DELETE.

    function initRowEvents(row, table) {
        var inputs = row.querySelectorAll(
            '[data-line-qty], [data-line-price], [data-line-disc-pct], [data-line-disc-amt], [data-line-vat-select]'
        );
        inputs.forEach(function (inp) {
            inp.addEventListener('input',  function () { updateTotals(table); });
            inp.addEventListener('change', function () { updateTotals(table); });
        });

        // Кнопка удаления строки: пересчёт после того, как строка исчезнет из DOM
        var delBtn = row.querySelector('[data-remove-line]');
        if (delBtn) {
            delBtn.addEventListener('click', function () {
                setTimeout(function () { updateTotals(table); }, 0);
            });
        }

        // Чекбокс DELETE (edit-режим): при отметке строка остаётся в DOM,
        // но её нужно вычесть из итогов
        var delChk = row.querySelector('input[name$="-DELETE"]');
        if (delChk) {
            delChk.addEventListener('change', function () { updateTotals(table); });
        }
    }

    // ─── Точка входа ──────────────────────────────────────────────────────

    document.addEventListener('DOMContentLoaded', function () {

        // Autocomplete для поля заказчика
        if (document.getElementById('id_customer')) {
            initAutocomplete('id_customer');
        }

        var table = document.getElementById('lines-table');
        if (!table) return;

        // Навешиваем события на строки, уже существующие при загрузке (edit-режим)
        table.querySelectorAll('[data-line-row]').forEach(function (row) {
            initRowEvents(row, table);
        });

        // Первичный пересчёт: сразу показывает/скрывает колонку НДС
        updateTotals(table);

        // MutationObserver отслеживает добавление новых строк кнопкой «+ Добавить строку»
        var tbody = table.querySelector('tbody');
        if (tbody) {
            var observer = new MutationObserver(function (mutations) {
                mutations.forEach(function (m) {
                    m.addedNodes.forEach(function (node) {
                        if (node.nodeType === 1 && node.matches('[data-line-row]')) {
                            initRowEvents(node, table);
                        }
                    });
                });
                updateTotals(table);
            });
            observer.observe(tbody, { childList: true });
        }
    });

})();
