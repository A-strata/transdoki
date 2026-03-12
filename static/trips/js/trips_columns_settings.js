(function () {
    function init() {
        const table = document.querySelector('[data-trips-table]');
        const settings = document.querySelector('[data-columns-settings]');
        const toggleBtn = document.querySelector('[data-columns-toggle]');
        const panel = document.querySelector('[data-columns-panel]');
        const list = document.querySelector('[data-columns-list]');
        const resetBtn = document.querySelector('[data-columns-reset]');

        if (!table || !settings || !toggleBtn || !panel || !list || !resetBtn) {
            console.warn('[columns] required elements not found');
            return;
        }

        const STORAGE_KEY = 'tms_trips_columns_v3';
        const LOCK_VISIBLE = new Set(['actions']);

        const ths = Array.from(table.querySelectorAll('thead th[data-col]'));
        const defaultOrder = ths.map(th => th.dataset.col);
        const labels = Object.fromEntries(ths.map(th => [th.dataset.col, th.textContent.trim()]));

        let state = { order: [...defaultOrder], hidden: [] };

        try {
            const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
            if (Array.isArray(saved.order)) {
                state.order = saved.order.filter(k => defaultOrder.includes(k));
            }
            if (Array.isArray(saved.hidden)) {
                state.hidden = saved.hidden.filter(k => defaultOrder.includes(k) && !LOCK_VISIBLE.has(k));
            }
            defaultOrder.forEach(k => {
                if (!state.order.includes(k)) state.order.push(k);
            });
        } catch (_) {}

        function saveState() {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        }

        function visibleColumnsCount() {
            const visible = state.order.filter(k => !state.hidden.includes(k)).length;
            return visible || 1;
        }

        function updateEmptyRowsColspan() {
            const span = visibleColumnsCount();
            table.querySelectorAll('.empty-row td').forEach(td => td.colSpan = span);
        }

        function applyColumns() {
            const rows = Array.from(table.querySelectorAll('tr'));

            rows.forEach((row) => {
                state.order.forEach((key) => {
                    const cell = row.querySelector('[data-col="' + key + '"]');
                    if (cell) row.appendChild(cell);
                });

                row.querySelectorAll('[data-col]').forEach((cell) => {
                    const key = cell.dataset.col;
                    cell.style.display = state.hidden.includes(key) ? 'none' : '';
                });
            });

            updateEmptyRowsColspan();
            document.dispatchEvent(new Event('tms:columns-updated'));
        }

        function moveKey(key, direction) {
            const i = state.order.indexOf(key);
            if (i === -1) return;
            const j = i + direction;
            if (j < 0 || j >= state.order.length) return;

            [state.order[i], state.order[j]] = [state.order[j], state.order[i]];
            saveState();
            renderPanel();
            applyColumns();
        }

        function renderPanel() {
            list.innerHTML = '';

            state.order.forEach((key, index) => {
                const li = document.createElement('li');
                li.className = 'columns-item';

                const left = document.createElement('div');
                left.className = 'columns-item-left';

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.checked = !state.hidden.includes(key);
                checkbox.disabled = LOCK_VISIBLE.has(key);

                checkbox.addEventListener('change', function () {
                    if (checkbox.checked) {
                        state.hidden = state.hidden.filter(k => k !== key);
                    } else if (!LOCK_VISIBLE.has(key)) {
                        if (!state.hidden.includes(key)) state.hidden.push(key);
                    }
                    saveState();
                    applyColumns();
                });

                const label = document.createElement('span');
                label.className = 'columns-item-label';
                label.textContent = labels[key] || key;

                left.appendChild(checkbox);
                left.appendChild(label);

                const actions = document.createElement('div');
                actions.className = 'columns-item-actions';

                const upBtn = document.createElement('button');
                upBtn.type = 'button';
                upBtn.className = 'columns-mini-btn';
                upBtn.textContent = '↑';
                upBtn.disabled = index === 0;
                upBtn.addEventListener('click', () => moveKey(key, -1));

                const downBtn = document.createElement('button');
                downBtn.type = 'button';
                downBtn.className = 'columns-mini-btn';
                downBtn.textContent = '↓';
                downBtn.disabled = index === state.order.length - 1;
                downBtn.addEventListener('click', () => moveKey(key, 1));

                actions.appendChild(upBtn);
                actions.appendChild(downBtn);

                li.appendChild(left);
                li.appendChild(actions);
                list.appendChild(li);
            });
        }

        // Открыть/закрыть панель
        toggleBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            panel.classList.toggle('is-hidden');
        });

        // Клик вне панели => закрыть
        document.addEventListener('click', function (e) {
            if (!settings.contains(e.target)) {
                panel.classList.add('is-hidden');
            }
        });

        // Не закрывать при клике внутри панели
        panel.addEventListener('click', function (e) {
            e.stopPropagation();
        });

        // Сброс
        resetBtn.addEventListener('click', function () {
            state = { order: [...defaultOrder], hidden: [] };
            saveState();
            renderPanel();
            applyColumns();
        });

        renderPanel();
        applyColumns();
        console.log('[columns] ready, items:', state.order.length);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();