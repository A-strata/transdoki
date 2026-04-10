(function () {
    function init() {
        var form = document.querySelector('[data-bank-filters]');
        if (!form) return;

        var searchInput = form.querySelector('[name="q"]');
        var calendarToggle = form.querySelector('[data-calendar-toggle]');
        var calendarFields = form.querySelector('[data-calendar-fields]');
        var dateFromInput = form.querySelector('[name="date_from"]');
        var dateToInput = form.querySelector('[name="date_to"]');
        var directionSelect = form.querySelector('[name="direction"]');
        var searchWrap = searchInput ? searchInput.closest('.search-field-wrap') : null;
        var searchClear = form.querySelector('[data-search-clear]');
        var contentContainer = document.querySelector('[data-list-content]');

        if (!contentContainer) return;

        var fetchController = null;
        var debounceTimer = null;

        // --- buildParams ---

        function buildParams(overrides) {
            var params = new URLSearchParams();

            var q = (overrides && 'q' in overrides)
                ? overrides.q
                : (searchInput ? searchInput.value.trim() : '');
            if (q) params.set('q', q);

            var dateFrom = (overrides && 'date_from' in overrides)
                ? overrides.date_from
                : (dateFromInput ? dateFromInput.value.trim() : '');
            if (dateFrom) params.set('date_from', dateFrom);

            var dateTo = (overrides && 'date_to' in overrides)
                ? overrides.date_to
                : (dateToInput ? dateToInput.value.trim() : '');
            if (dateTo) params.set('date_to', dateTo);

            var direction = (overrides && 'direction' in overrides)
                ? overrides.direction
                : (directionSelect ? directionSelect.value : '');
            if (direction) params.set('direction', direction);

            return params;
        }

        // --- fetchList ---

        function fetchList(params) {
            var qs = params.toString();
            var urlStr = window.location.pathname + (qs ? '?' + qs : '');

            if (fetchController) fetchController.abort();
            fetchController = new AbortController();

            contentContainer.classList.add('is-loading');

            fetch(urlStr, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                signal: fetchController.signal
            })
            .then(function (r) {
                if (r.status === 401 || r.status === 403) {
                    location.href = '/accounts/login/?next=' + encodeURIComponent(location.pathname);
                    return;
                }
                if (!r.ok) throw new Error('server_error');
                return r.text();
            })
            .then(function (html) {
                if (!html) return;

                contentContainer.innerHTML = html;
                contentContainer.classList.remove('is-loading');

                history.pushState(null, '', urlStr);
            })
            .catch(function (err) {
                if (err.name === 'AbortError') return;

                contentContainer.classList.remove('is-loading');
                if (err.message === 'server_error') {
                    contentContainer.innerHTML =
                        '<div class="alert alert-error">Произошла ошибка на сервере. ' +
                        '<button type="button" class="tms-btn tms-btn-secondary tms-btn-sm" ' +
                        'onclick="location.reload()">Обновить</button></div>';
                } else {
                    contentContainer.innerHTML =
                        '<div class="alert alert-error">Не удалось загрузить данные. ' +
                        '<button type="button" class="tms-btn tms-btn-secondary tms-btn-sm" ' +
                        'onclick="location.reload()">Обновить</button></div>';
                }
            });
        }

        // --- Поиск ---

        function updateSearchState() {
            if (!searchInput || !searchWrap) return;
            searchWrap.classList.toggle('is-filtered', !!searchInput.value.trim());
        }

        if (searchInput) {
            searchInput.addEventListener('input', function () {
                updateSearchState();
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(function () {
                    fetchList(buildParams());
                }, 300);
            });

            searchInput.addEventListener('keydown', function (e) {
                if (e.key === 'Escape') {
                    searchInput.value = '';
                    updateSearchState();
                    fetchList(buildParams());
                }
            });
        }

        if (searchClear) {
            searchClear.addEventListener('click', function () {
                if (searchInput) searchInput.value = '';
                updateSearchState();
                fetchList(buildParams());
                if (searchInput) searchInput.focus();
            });
        }

        // --- Календарь ---

        var calendarOpen = false;

        function hasAnyDate() {
            return !!(
                (dateFromInput && dateFromInput.value) ||
                (dateToInput && dateToInput.value)
            );
        }

        function updateDateFieldStates() {
            if (dateFromInput) dateFromInput.classList.toggle('is-filled', !!dateFromInput.value);
            if (dateToInput) dateToInput.classList.toggle('is-filled', !!dateToInput.value);
        }

        function updateCalendarToggleState() {
            if (!calendarToggle) return;
            calendarToggle.setAttribute('aria-expanded', (hasAnyDate() || calendarOpen) ? 'true' : 'false');
            updateDateFieldStates();
        }

        function openCalendarFields() {
            if (!calendarFields) return;
            calendarOpen = true;
            calendarFields.classList.add('is-visible');
            updateCalendarToggleState();
        }

        function syncCalendarVisibility() {
            if (!calendarFields) return;
            if (hasAnyDate()) {
                calendarOpen = true;
                calendarFields.classList.add('is-visible');
            } else {
                calendarOpen = false;
                calendarFields.classList.remove('is-visible');
            }
            updateCalendarToggleState();
        }

        if (calendarToggle) {
            calendarToggle.addEventListener('click', function (e) {
                e.stopPropagation();
                if (calendarOpen) {
                    calendarOpen = false;
                    calendarFields.classList.remove('is-visible');
                    updateCalendarToggleState();
                } else {
                    openCalendarFields();
                    if (dateFromInput && !dateFromInput.value) {
                        dateFromInput.focus();
                    } else if (dateToInput && !dateToInput.value) {
                        dateToInput.focus();
                    } else if (dateFromInput) {
                        dateFromInput.focus();
                    }
                }
            });
        }

        function onDateChange() {
            syncCalendarVisibility();
            fetchList(buildParams());
        }

        if (dateFromInput) {
            dateFromInput.addEventListener('change', onDateChange);
            dateFromInput.addEventListener('input', onDateChange);
        }
        if (dateToInput) {
            dateToInput.addEventListener('change', onDateChange);
            dateToInput.addEventListener('input', onDateChange);
        }

        // --- Direction select ---

        if (directionSelect) {
            directionSelect.addEventListener('change', function () {
                fetchList(buildParams());
            });
        }

        // --- Форма submit ---

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            fetchList(buildParams());
        });

        // --- popstate ---

        function restoreFormFromParams(params) {
            if (searchInput) searchInput.value = params.get('q') || '';
            if (dateFromInput) dateFromInput.value = params.get('date_from') || '';
            if (dateToInput) dateToInput.value = params.get('date_to') || '';
            if (directionSelect) directionSelect.value = params.get('direction') || '';

            updateSearchState();
            syncCalendarVisibility();
        }

        window.addEventListener('popstate', function () {
            var params = new URLSearchParams(window.location.search);
            restoreFormFromParams(params);
            fetchList(params);
        });

        // --- Autocomplete в модалке платежа ---

        if (typeof initAutocomplete === 'function') {
            initAutocomplete('pm_organization');
        }

        // --- Инициализация ---

        updateSearchState();
        syncCalendarVisibility();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
