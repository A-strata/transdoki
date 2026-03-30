// Управление колонками:
// - изменение ширины перетаскиванием границы
// - показ / скрытие колонок через меню "Вид"
// - изменение порядка через кнопки ↑ / ↓
(function () {
    function init() {
        const table = document.querySelector('[data-trips-table]');
        const visibilityRoot = document.querySelector('[data-columns-visibility]');
        const visibilityToggle = document.querySelector('[data-visibility-toggle]');
        const visibilityPanel = document.querySelector('[data-visibility-panel]');
        const visibilityList = document.querySelector('[data-visibility-list]');
        const visibilityReset = document.querySelector('[data-visibility-reset]');

        if (!table || !visibilityRoot || !visibilityToggle || !visibilityPanel || !visibilityList || !visibilityReset) {
            return;
        }

        const STORAGE_KEY = 'tms_trips_columns_v7';
        const MIN_COL_WIDTH = 80;
        const ROW_ACTIONS_WIDTH = 100;

        // Колонки, скрытые по умолчанию при первом визите
        const DEFAULT_HIDDEN = [
            'consignor', 'consignee', 'trailer',
            'planned_loading_date', 'planned_unloading_date',
            'cargo', 'weight',
            'client_cost', 'carrier_cost',
            'client_payment_method', 'payment_condition',
            'carrier_payment_method', 'comments'
        ];

        const ths = Array.from(table.querySelectorAll('thead th[data-col]'));
        const defaultOrder = ths.map(th => th.dataset.col);
        const labels = Object.fromEntries(ths.map(th => [th.dataset.col, th.textContent.trim()]));

        let state = {
            order: [...defaultOrder],
            hidden: [...DEFAULT_HIDDEN],
            widths: {}
        };

        try {
            const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');

            if (saved) {
                if (Array.isArray(saved.order)) {
                    state.order = saved.order.filter(key => defaultOrder.includes(key));
                }

                if (Array.isArray(saved.hidden)) {
                    state.hidden = saved.hidden.filter(key => defaultOrder.includes(key));
                }

                if (saved.widths && typeof saved.widths === 'object') {
                    state.widths = saved.widths;
                }
            }
        } catch (_) {}

        // Добавить новые колонки, которых нет в сохранённом порядке
        defaultOrder.forEach(key => {
            if (!state.order.includes(key)) {
                state.order.push(key);
            }
        });

        function saveState() {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        }

        function getHeaderCell(key) {
            return table.querySelector(`thead th[data-col="${key}"]`);
        }

        function getCellsByKey(key) {
            return Array.from(table.querySelectorAll(`[data-col="${key}"]`));
        }

        function visibleColumnsCount() {
            return state.order.filter(key => !state.hidden.includes(key)).length || 1;
        }

        function updateEmptyRowsColspan() {
            const span = visibleColumnsCount() + 2; // +1 spacer, +1 row-actions
            table.querySelectorAll('.empty-row td').forEach(td => {
                td.colSpan = span;
            });
        }

        function measureHeaderWidth(th) {
            const text = th.dataset.labelText || th.textContent.trim();

            const probe = document.createElement('span');
            probe.textContent = text;
            probe.style.position = 'absolute';
            probe.style.visibility = 'hidden';
            probe.style.whiteSpace = 'nowrap';
            probe.style.fontSize = getComputedStyle(th).fontSize;
            probe.style.fontWeight = getComputedStyle(th).fontWeight;
            probe.style.letterSpacing = getComputedStyle(th).letterSpacing;
            probe.style.textTransform = getComputedStyle(th).textTransform;

            document.body.appendChild(probe);
            const width = Math.ceil(probe.getBoundingClientRect().width) + 34;
            probe.remove();

            return Math.max(width, MIN_COL_WIDTH);
        }

        function ensureDefaultWidths() {
            state.order.forEach(key => {
                if (!state.widths[key]) {
                    const th = getHeaderCell(key);
                    if (th) {
                        state.widths[key] = measureHeaderWidth(th);
                    }
                }
            });
        }

        function applyOrder() {
            const rows = Array.from(table.querySelectorAll('tr'));

            rows.forEach(row => {
                if (row.classList.contains('empty-row')) return;

                state.order.forEach(key => {
                    const cell = row.querySelector(`[data-col="${key}"]`);
                    if (cell) row.appendChild(cell);
                });

                const actionsCell = row.querySelector('[data-row-actions], th.row-actions-cell');
                if (actionsCell) row.appendChild(actionsCell);

                const spacer = row.querySelector('.col-spacer');
                if (spacer) row.appendChild(spacer);
            });
        }

        function ensureSpacerCells() {
            table.querySelectorAll('tr').forEach(row => {
                if (row.classList.contains('empty-row')) return;
                if (row.querySelector('.col-spacer')) return;

                const isHead = row.closest('thead') !== null;
                const spacer = document.createElement(isHead ? 'th' : 'td');
                spacer.className = 'col-spacer';
                row.appendChild(spacer);
            });
        }

        function applyWidths() {
            let totalWidth = 0;

            state.order.forEach(key => {
                if (state.hidden.includes(key)) return;

                const width = Math.max(Number(state.widths[key] || MIN_COL_WIDTH), MIN_COL_WIDTH);
                totalWidth += width;

                getCellsByKey(key).forEach(cell => {
                    cell.style.width = width + 'px';
                    cell.style.minWidth = width + 'px';
                    cell.style.maxWidth = width + 'px';
                });
            });

            totalWidth += ROW_ACTIONS_WIDTH;

            const containerWidth = table.closest('.table-wrap').clientWidth;
            table.style.width = Math.max(totalWidth, containerWidth) + 'px';
        }

        function applyVisibility() {
            state.order.forEach(key => {
                const isHidden = state.hidden.includes(key);

                getCellsByKey(key).forEach(cell => {
                    cell.style.display = isHidden ? 'none' : '';
                });
            });
        }

        function applyAll() {
            ensureDefaultWidths();
            applyOrder();
            ensureSpacerCells();
            applyVisibility();
            applyWidths();
            updateEmptyRowsColspan();
            document.dispatchEvent(new Event('tms:columns-updated'));
        }

        function moveColumn(key, direction) {
            const index = state.order.indexOf(key);
            if (index === -1) return;

            const nextIndex = index + direction;
            if (nextIndex < 0 || nextIndex >= state.order.length) return;

            [state.order[index], state.order[nextIndex]] = [state.order[nextIndex], state.order[index]];

            saveState();
            renderVisibilityMenu();
            applyAll();
        }

        function renderVisibilityMenu() {
            visibilityList.innerHTML = '';

            state.order.forEach((key, index) => {
                const li = document.createElement('li');
                li.className = 'visibility-item';

                const row = document.createElement('div');
                row.className = 'visibility-row';

                const label = document.createElement('label');
                label.className = 'visibility-label';

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.checked = !state.hidden.includes(key);

                checkbox.addEventListener('change', function () {
                    if (checkbox.checked) {
                        state.hidden = state.hidden.filter(k => k !== key);
                    } else {
                        if (!state.hidden.includes(key)) {
                            state.hidden.push(key);
                        }
                    }

                    saveState();
                    applyAll();
                });

                const text = document.createElement('span');
                text.textContent = labels[key] || key;

                label.appendChild(checkbox);
                label.appendChild(text);

                const actions = document.createElement('div');
                actions.className = 'visibility-item-actions';

                const upBtn = document.createElement('button');
                upBtn.type = 'button';
                upBtn.className = 'visibility-move-btn';
                upBtn.textContent = '↑';
                upBtn.disabled = index === 0;
                upBtn.addEventListener('click', function () {
                    moveColumn(key, -1);
                });

                const downBtn = document.createElement('button');
                downBtn.type = 'button';
                downBtn.className = 'visibility-move-btn';
                downBtn.textContent = '↓';
                downBtn.disabled = index === state.order.length - 1;
                downBtn.addEventListener('click', function () {
                    moveColumn(key, 1);
                });

                actions.appendChild(upBtn);
                actions.appendChild(downBtn);

                row.appendChild(label);
                row.appendChild(actions);
                li.appendChild(row);
                visibilityList.appendChild(li);
            });
        }

        // Панель "Вид"
        function closeVisibilityPanel() {
            visibilityPanel.classList.add('is-hidden');
            visibilityToggle.setAttribute('aria-expanded', 'false');
        }

        visibilityToggle.addEventListener('click', function (e) {
            e.stopPropagation();

            const willOpen = visibilityPanel.classList.contains('is-hidden');

            if (willOpen) {
                document.dispatchEvent(new CustomEvent('tms:dropdown-open', { detail: { id: 'visibility-panel' } }));
                visibilityPanel.classList.remove('align-left');

                visibilityPanel.classList.remove('is-hidden');
                const rect = visibilityPanel.getBoundingClientRect();

                if (rect.left < 8 || rect.right > window.innerWidth - 8) {
                    visibilityPanel.classList.add('align-left');
                }
            } else {
                visibilityPanel.classList.add('is-hidden');
            }

            const hidden = visibilityPanel.classList.contains('is-hidden');
            visibilityToggle.setAttribute('aria-expanded', hidden ? 'false' : 'true');
        });

        document.addEventListener('tms:dropdown-open', function (e) {
            if (e.detail.id !== 'visibility-panel') closeVisibilityPanel();
        });

        visibilityPanel.addEventListener('click', function (e) {
            e.stopPropagation();
        });

        document.addEventListener('click', function (e) {
            if (!visibilityRoot.contains(e.target)) {
                visibilityPanel.classList.add('is-hidden');
                visibilityToggle.setAttribute('aria-expanded', 'false');
            }
        });

        visibilityReset.addEventListener('click', function () {
            state = {
                order: [...defaultOrder],
                hidden: [...DEFAULT_HIDDEN],
                widths: {}
            };

            saveState();
            renderVisibilityMenu();
            applyAll();
        });

        // Resize колонок
        function getLastVisibleKey() {
            for (let i = state.order.length - 1; i >= 0; i--) {
                if (!state.hidden.includes(state.order[i])) return state.order[i];
            }
            return null;
        }

        function attachResizeHandle(handle, getTargetKey, getTargetTh) {
            let startX = 0;
            let startWidth = 0;
            let resizing = false;
            let targetKey = null;
            let targetTh = null;

            handle.addEventListener('mousedown', function (e) {
                e.preventDefault();
                e.stopPropagation();

                targetKey = getTargetKey();
                targetTh = getTargetTh(targetKey);
                if (!targetKey || !targetTh) return;

                resizing = true;
                startX = e.clientX;
                startWidth = targetTh.getBoundingClientRect().width;

                targetTh.classList.add('is-resizing');
                document.body.style.cursor = 'col-resize';
                document.body.style.userSelect = 'none';

                function onMove(ev) {
                    if (!resizing) return;

                    const nextWidth = Math.max(
                        MIN_COL_WIDTH,
                        Math.round(startWidth + (ev.clientX - startX))
                    );

                    state.widths[targetKey] = nextWidth;
                    applyWidths();
                }

                function onUp() {
                    if (!resizing) return;

                    resizing = false;
                    if (targetTh) targetTh.classList.remove('is-resizing');
                    document.body.style.cursor = '';
                    document.body.style.userSelect = '';

                    saveState();

                    document.removeEventListener('mousemove', onMove);
                    document.removeEventListener('mouseup', onUp);
                }

                document.addEventListener('mousemove', onMove);
                document.addEventListener('mouseup', onUp);
            });
        }

        function bindResizeHandles() {
            const headers = Array.from(table.querySelectorAll('thead th[data-col]'));

            headers.forEach(th => {
                const key = th.dataset.col;

                const oldHandle = th.querySelector('.col-resize-handle');
                if (oldHandle) oldHandle.remove();

                th.dataset.labelText = th.textContent.trim();

                const handle = document.createElement('span');
                handle.className = 'col-resize-handle';
                handle.setAttribute('aria-hidden', 'true');
                th.appendChild(handle);

                attachResizeHandle(
                    handle,
                    function () { return key; },
                    function () { return th; }
                );
            });

            // Handle на левой стороне row-actions header —
            // ресайзит последний видимый data-столбец
            var actionsHeader = table.querySelector('thead th.row-actions-cell');
            if (actionsHeader) {
                var oldEdge = actionsHeader.querySelector('.col-resize-edge');
                if (oldEdge) oldEdge.remove();

                var edge = document.createElement('span');
                edge.className = 'col-resize-edge';
                edge.setAttribute('aria-hidden', 'true');
                actionsHeader.appendChild(edge);

                attachResizeHandle(
                    edge,
                    getLastVisibleKey,
                    function (key) { return key ? getHeaderCell(key) : null; }
                );

                // Показывать edge-handle при hover на последний видимый столбец
                headers.forEach(function (th) {
                    th.addEventListener('mouseenter', function () {
                        if (th.dataset.col === getLastVisibleKey()) {
                            actionsHeader.classList.add('is-edge-hover');
                        }
                    });
                    th.addEventListener('mouseleave', function () {
                        actionsHeader.classList.remove('is-edge-hover');
                    });
                });
            }
        }

        renderVisibilityMenu();
        applyAll();
        bindResizeHandles();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
