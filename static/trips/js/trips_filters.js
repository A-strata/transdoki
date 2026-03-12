// Фильтры таблицы (поиск по ВСЕМ колонкам data-col, кроме actions)
(function () {
    function init() {
        const table = document.querySelector('[data-trips-table]');
        const filtersBar = document.querySelector('[data-trip-filters]');
        if (!table || !filtersBar) return;

        const tbody = table.querySelector('tbody');
        const allRows = Array.from(tbody.querySelectorAll('tr[data-trip-row]'));

        const qInput = filtersBar.querySelector('[data-filter="q"]');
        const clientSelect = filtersBar.querySelector('[data-filter="client"]');
        const carrierSelect = filtersBar.querySelector('[data-filter="carrier"]');
        const dateFromInput = filtersBar.querySelector('[data-filter="date_from"]');
        const dateToInput = filtersBar.querySelector('[data-filter="date_to"]');
        const resetBtn = filtersBar.querySelector('[data-filter="reset"]');
        const meta = filtersBar.querySelector('[data-filter="meta"]');

        if (!qInput || !clientSelect || !carrierSelect || !dateFromInput || !dateToInput || !resetBtn || !meta) {
            return;
        }

        function cellTextByKey(row, key) {
            return (row.querySelector('[data-col="' + key + '"]')?.textContent || '').trim();
        }

        function normalize(s) {
            return (s || '').toLowerCase().replace(/\s+/g, ' ').trim();
        }

        function parseRuDate(str) {
            // поддержка "dd.mm.yyyy" и "dd.mm.yyyy HH:MM" (берем только дату)
            const raw = (str || '').trim().slice(0, 10);
            const m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(raw);
            if (!m) return null;
            return new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]));
        }

        function toDateInputValueDate(v) {
            if (!v) return null;
            const [y, m, d] = v.split('-').map(Number);
            return new Date(y, m - 1, d);
        }

        function fillSelect(selectEl, values) {
            values.sort((a, b) => a.localeCompare(b, 'ru'));
            for (const val of values) {
                const opt = document.createElement('option');
                opt.value = val;
                opt.textContent = val;
                selectEl.appendChild(opt);
            }
        }

        function visibleColumnsCount() {
            const visible = Array.from(table.querySelectorAll('thead th[data-col]'))
                .filter(th => th.style.display !== 'none').length;
            return visible || 1;
        }

        function updateEmptyRowsColspan() {
            const span = visibleColumnsCount();
            table.querySelectorAll('.empty-row td').forEach(td => td.colSpan = span);
        }

        // Текст для поиска: все колонки строки, кроме actions
        function rowSearchText(row) {
            const parts = Array.from(row.querySelectorAll('td[data-col]'))
                .filter(td => td.dataset.col !== 'actions')
                .map(td => td.textContent || '');
            return normalize(parts.join(' '));
        }

        // Селекты по-прежнему из конкретных колонок
        fillSelect(clientSelect, [...new Set(allRows.map(r => cellTextByKey(r, 'client')).filter(Boolean))]);
        fillSelect(carrierSelect, [...new Set(allRows.map(r => cellTextByKey(r, 'carrier')).filter(Boolean))]);

        let noResultsRow = null;
        if (allRows.length) {
            noResultsRow = document.createElement('tr');
            noResultsRow.className = 'empty-row';
            noResultsRow.style.display = 'none';
            noResultsRow.innerHTML = '<td colspan="' + visibleColumnsCount() + '">Ничего не найдено по текущим фильтрам</td>';
            tbody.appendChild(noResultsRow);
        }

        function applyFilters() {
            updateEmptyRowsColspan();

            if (!allRows.length) {
                meta.textContent = 'Показано: 0 из 0';
                return;
            }

            const q = normalize(qInput.value);
            const client = clientSelect.value;
            const carrier = carrierSelect.value;
            const dateFrom = toDateInputValueDate(dateFromInput.value);
            const dateTo = toDateInputValueDate(dateToInput.value);

            let visibleCount = 0;

            allRows.forEach(row => {
                const rowClient = cellTextByKey(row, 'client');
                const rowCarrier = cellTextByKey(row, 'carrier');
                const rowDate = parseRuDate(cellTextByKey(row, 'date_of_trip'));

                // Поиск теперь по всем полям строки
                const haystack = rowSearchText(row);

                const matchQ = !q || haystack.includes(q);
                const matchClient = !client || rowClient === client;
                const matchCarrier = !carrier || rowCarrier === carrier;
                const matchDateFrom = !dateFrom || (rowDate && rowDate >= dateFrom);
                const matchDateTo = !dateTo || (rowDate && rowDate <= dateTo);

                const isVisible = matchQ && matchClient && matchCarrier && matchDateFrom && matchDateTo;
                row.style.display = isVisible ? '' : 'none';
                if (isVisible) visibleCount++;
            });

            if (noResultsRow) {
                noResultsRow.style.display = visibleCount ? 'none' : '';
                const td = noResultsRow.querySelector('td');
                if (td) td.colSpan = visibleColumnsCount();
            }

            meta.textContent = `Показано: ${visibleCount} из ${allRows.length}`;
        }

        [qInput, clientSelect, carrierSelect, dateFromInput, dateToInput].forEach(el => {
            el.addEventListener('input', applyFilters);
            el.addEventListener('change', applyFilters);
        });

        resetBtn.addEventListener('click', function () {
            qInput.value = '';
            clientSelect.value = '';
            carrierSelect.value = '';
            dateFromInput.value = '';
            dateToInput.value = '';
            applyFilters();
        });

        document.addEventListener('tms:columns-updated', applyFilters);

        applyFilters();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();