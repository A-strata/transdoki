(function () {
    function init() {
        const form = document.querySelector('[data-trip-filters]');
        const toggle = document.querySelector('[data-filters-panel-toggle]');
        const panel = document.querySelector('[data-filter-dropdown]');
        const wrap = document.querySelector('[data-filter-dropdown-wrap]');
        const badge = document.querySelector('[data-filters-active-badge]');
        const countNode = document.querySelector('[data-filters-active-count]');
        const resetBtn = form ? form.querySelector('[data-filter="reset"]') : null;

        if (!form || !toggle || !panel) return;

        function getField(name) {
            return form.querySelector(`[name="${name}"]`);
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
            if (!badge || !countNode) return;
            const count = getAppliedGroupsCount();
            if (count > 0) {
                countNode.textContent = String(count);
                badge.hidden = false;
            } else {
                badge.hidden = true;
            }
        }

        function openPanel() {
            document.dispatchEvent(new CustomEvent('tms:dropdown-open', { detail: { id: 'filters-panel' } }));
            panel.classList.add('is-open');
            toggle.setAttribute('aria-expanded', 'true');
        }

        function closePanel() {
            panel.classList.remove('is-open');
            toggle.setAttribute('aria-expanded', 'false');
        }

        toggle.addEventListener('click', function (e) {
            e.stopPropagation();
            panel.classList.contains('is-open') ? closePanel() : openPanel();
        });

        document.addEventListener('click', function (e) {
            if (wrap && !wrap.contains(e.target)) closePanel();
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closePanel();
        });

        document.addEventListener('tms:dropdown-open', function (e) {
            if (e.detail.id !== 'filters-panel') closePanel();
        });

        if (resetBtn) {
            resetBtn.addEventListener('click', function () {
                requestAnimationFrame(updateActiveBadge);
            });
        }

        window.addEventListener('pageshow', updateActiveBadge);
        updateActiveBadge();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
