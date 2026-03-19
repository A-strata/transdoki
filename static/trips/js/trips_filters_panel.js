(function () {
    function init() {
        const panel = document.querySelector('[data-trip-filters]');
        const toggle = document.querySelector('[data-filters-panel-toggle]');
        const badge = document.querySelector('[data-filters-active-badge]');
        const countNode = document.querySelector('[data-filters-active-count]');
        const resetBtn = panel ? panel.querySelector('[data-filter="reset"]') : null;

        if (!panel || !toggle) return;

        const STORAGE_KEY = 'tms_trips_filters_panel_v2';

        function getField(name) {
            return panel.querySelector(`[name="${name}"]`);
        }

        function hasAppliedChronologyFilter() {
            const dateFrom = getField('date_from');
            const dateTo = getField('date_to');

            return !!(
                (dateFrom && String(dateFrom.value || '').trim() !== '') ||
                (dateTo && String(dateTo.value || '').trim() !== '')
            );
        }

        function hasAppliedContractorFilter() {
            const contractorQuery = getField('contractor_query');
            return !!(contractorQuery && String(contractorQuery.value || '').trim() !== '');
        }

        function getAppliedGroupsCount() {
            let count = 0;

            if (hasAppliedChronologyFilter()) count += 1;
            if (hasAppliedContractorFilter()) count += 1;

            return count;
        }

        function updateActiveBadge() {
            const count = getAppliedGroupsCount();

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

        if (resetBtn) {
            resetBtn.addEventListener('click', function () {
                requestAnimationFrame(updateActiveBadge);
            });
        }

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