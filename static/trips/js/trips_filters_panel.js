(function () {
    function init() {
        const panel = document.querySelector('[data-trip-filters]');
        const toggle = document.querySelector('[data-filters-panel-toggle]');
        const badge = document.querySelector('[data-filters-active-badge]');
        const countNode = document.querySelector('[data-filters-active-count]');

        if (!panel || !toggle) return;

        const STORAGE_KEY = 'tms_trips_filters_panel_v1';

        function getFilterFields() {
            return Array.from(panel.querySelectorAll('[data-filter]')).filter((el) => el.name && el.type !== 'hidden');
        }

        function getActiveFiltersCount() {
            let count = 0;

            getFilterFields().forEach((el) => {
                if (el.tagName === 'SELECT') {
                    if (el.value !== '') count += 1;
                    return;
                }

                if (el.type === 'checkbox' || el.type === 'radio') {
                    if (el.checked) count += 1;
                    return;
                }

                if ((el.value || '').trim() !== '') count += 1;
            });

            return count;
        }

        function updateActiveBadge() {
            const count = getActiveFiltersCount();

            if (!badge || !countNode) return;

            if (count > 0) {
                countNode.textContent = String(count);
                badge.hidden = false;
            } else {
                badge.hidden = true;
            }
        }

        function setCollapsed(collapsed) {
            panel.classList.toggle('is-collapsed', collapsed);
            toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
            toggle.textContent = collapsed ? 'Развернуть фильтры' : 'Свернуть фильтры';
            localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0');
        }

        function getInitialCollapsed() {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (saved === '1') return true;
            if (saved === '0') return false;

            return window.innerHeight <= 900;
        }

        toggle.addEventListener('click', function () {
            const collapsed = panel.classList.contains('is-collapsed');
            setCollapsed(!collapsed);
        });

        panel.addEventListener('input', updateActiveBadge);
        panel.addEventListener('change', updateActiveBadge);

        document.addEventListener('DOMContentLoaded', updateActiveBadge);
        window.addEventListener('pageshow', updateActiveBadge);

        setCollapsed(getInitialCollapsed());
        updateActiveBadge();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();