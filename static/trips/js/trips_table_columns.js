// Управление колонками:
// - изменение ширины перетаскиванием границы
// - показ / скрытие колонок через меню "Вид"
// - колонка actions всегда справа и не скрывается
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

        const STORAGE_KEY = 'tms_trips_columns_v4';
        const LOCK_RIGHT = 'actions';
        const MIN_COL_WIDTH = 80;
        const ACTIONS_WIDTH = 190;

        const ths = Array.from(table.querySelectorAll('thead th[data-col]'));
        const defaultOrder = ths.map(th => th.dataset.col);
        const labels = Object.fromEntries(ths.map(th => [th.dataset.col, th.textContent.trim()]));

        let state = {
            order: [...defaultOrder],
            hidden: [],
            widths: {}
        };

        try {
            const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');

            if (Array.isArray(saved.order)) {
                state.order = saved.order.filter(key => defaultOrder.includes(key));
            }

            if (Array.isArray(saved.hidden)) {
                state.hidden = saved.hidden.filter(key => defaultOrder.includes(key) && key !== LOCK_RIGHT);
            }

            if (saved.widths && typeof saved.widths === 'object') {
                state.widths = saved.widths;
            }
        } catch (_) {}

        // actions всегда последняя
        state.order = state.order.filter(key => key !== LOCK_RIGHT);
        defaultOrder.forEach(key => {
            if (key !== LOCK_RIGHT && !state.order.includes(key)) {
                state.order.push(key);
            }
        });
        state.order.push(LOCK_RIGHT);

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
            const span = visibleColumnsCount();
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
                if (key === LOCK_RIGHT) {
                    state.widths[key] = ACTIONS_WIDTH;
                    return;
                }

                if (!state.widths[key]) {
                    const th = getHeaderCell(key);
                    if (th) {
                        state.widths[key] = measureHeaderWidth(th);
                    }
                }
            });
        }

        function applyWidths() {
            state.order.forEach(key => {
                const width = key === LOCK_RIGHT
                    ? ACTIONS_WIDTH
                    : Math.max(Number(state.widths[key] || MIN_COL_WIDTH), MIN_COL_WIDTH);

                getCellsByKey(key).forEach(cell => {
                    cell.style.width = width + 'px';
                    cell.style.minWidth = width + 'px';
                    cell.style.maxWidth = width + 'px';
                });
            });
        }

        function applyVisibility() {
            state.order.forEach(key => {
                const isHidden = key !== LOCK_RIGHT && state.hidden.includes(key);

                getCellsByKey(key).forEach(cell => {
                    cell.style.display = isHidden ? 'none' : '';
                });
            });
        }

        // Пока порядок не меняем, просто обновляем видимость и ширину
        function applyAll() {
            ensureDefaultWidths();
            applyVisibility();
            applyWidths();
            updateEmptyRowsColspan();
            document.dispatchEvent(new Event('tms:columns-updated'));
        }

        function renderVisibilityMenu() {
            visibilityList.innerHTML = '';

            state.order.forEach(key => {
                if (key === LOCK_RIGHT) return;

                const li = document.createElement('li');
                li.className = 'visibility-item';

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
                li.appendChild(label);
                visibilityList.appendChild(li);
            });
        }

        // Панель "Вид"
        visibilityToggle.addEventListener('click', function (e) {
            e.stopPropagation();
            const hidden = visibilityPanel.classList.toggle('is-hidden');
            visibilityToggle.setAttribute('aria-expanded', hidden ? 'false' : 'true');
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
                hidden: [],
                widths: {}
            };

            state.order = state.order.filter(key => key !== LOCK_RIGHT);
            state.order.push(LOCK_RIGHT);

            saveState();
            renderVisibilityMenu();
            applyAll();
        });

        // Resize колонок
        function bindResizeHandles() {
            const headers = Array.from(table.querySelectorAll('thead th[data-col]'));

            headers.forEach(th => {
                const key = th.dataset.col;

                const oldHandle = th.querySelector('.col-resize-handle');
                if (oldHandle) oldHandle.remove();

                if (key === LOCK_RIGHT) return;

                th.dataset.labelText = th.textContent.trim();

                const handle = document.createElement('span');
                handle.className = 'col-resize-handle';
                handle.setAttribute('aria-hidden', 'true');
                th.appendChild(handle);

                let startX = 0;
                let startWidth = 0;
                let resizing = false;

                handle.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    e.stopPropagation();

                    resizing = true;
                    startX = e.clientX;
                    startWidth = th.getBoundingClientRect().width;

                    th.classList.add('is-resizing');
                    document.body.style.cursor = 'col-resize';
                    document.body.style.userSelect = 'none';

                    function onMove(ev) {
                        if (!resizing) return;

                        const nextWidth = Math.max(
                            MIN_COL_WIDTH,
                            Math.round(startWidth + (ev.clientX - startX))
                        );

                        state.widths[key] = nextWidth;
                        applyWidths();
                    }

                    function onUp() {
                        if (!resizing) return;

                        resizing = false;
                        th.classList.remove('is-resizing');
                        document.body.style.cursor = '';
                        document.body.style.userSelect = '';

                        saveState();

                        document.removeEventListener('mousemove', onMove);
                        document.removeEventListener('mouseup', onUp);
                    }

                    document.addEventListener('mousemove', onMove);
                    document.addEventListener('mouseup', onUp);
                });
            });
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