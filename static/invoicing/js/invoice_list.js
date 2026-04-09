(function () {
    var STORAGE_KEY = 'tms_invoices_page_size';
    var DEFAULT_PAGE_SIZE = '25';

    function init() {
        var form = document.querySelector('[data-invoice-filters]');
        if (!form) return;

        var searchInput = form.querySelector('[name="q"]');
        var calendarToggle = form.querySelector('[data-calendar-toggle]');
        var calendarFields = form.querySelector('[data-calendar-fields]');
        var dateFromInput = form.querySelector('[name="date_from"]');
        var dateToInput = form.querySelector('[name="date_to"]');
        var searchWrap = searchInput ? searchInput.closest('.search-field-wrap') : null;
        var searchClear = form.querySelector('[data-search-clear]');
        var pageSizeSelect = document.querySelector('[data-page-size-select]');
        var contentContainer = document.querySelector('[data-list-content]');

        if (!contentContainer) return;

        var fetchController = null;
        var debounceTimer = null;

        // Восстановить page_size из localStorage при первом визите
        if (pageSizeSelect) {
            var urlParams = new URLSearchParams(window.location.search);
            if (!urlParams.has('page_size')) {
                var saved = localStorage.getItem(STORAGE_KEY);
                if (saved && saved !== pageSizeSelect.value) {
                    urlParams.set('page_size', saved);
                    urlParams.set('page', '1');
                    window.location.search = urlParams.toString();
                    return;
                }
            }
        }

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

            var ps;
            if (overrides && 'page_size' in overrides) {
                ps = overrides.page_size;
            } else if (pageSizeSelect) {
                ps = pageSizeSelect.value;
            }
            if (ps && String(ps) !== DEFAULT_PAGE_SIZE) {
                params.set('page_size', ps);
            }

            if (overrides && overrides.page) {
                params.set('page', overrides.page);
            }

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

                bindPageSizeSelect();
                bindPaginationLinks();
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
            var hasValue = !!searchInput.value.trim();
            searchWrap.classList.toggle('is-filtered', hasValue);
        }

        if (searchInput) {
            searchInput.addEventListener('input', function () {
                updateSearchState();
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(function () {
                    fetchList(buildParams({ page: '' }));
                }, 300);
            });

            searchInput.addEventListener('keydown', function (e) {
                if (e.key === 'Escape') {
                    searchInput.value = '';
                    updateSearchState();
                    fetchList(buildParams({ page: '' }));
                }
            });
        }

        if (searchClear) {
            searchClear.addEventListener('click', function () {
                if (searchInput) searchInput.value = '';
                updateSearchState();
                fetchList(buildParams({ page: '' }));
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
            fetchList(buildParams({ page: '' }));
        }

        if (dateFromInput) {
            dateFromInput.addEventListener('change', onDateChange);
            dateFromInput.addEventListener('input', onDateChange);
        }
        if (dateToInput) {
            dateToInput.addEventListener('change', onDateChange);
            dateToInput.addEventListener('input', onDateChange);
        }

        // --- Форма submit ---

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            fetchList(buildParams({ page: '' }));
        });

        // --- Page size ---

        function bindPageSizeSelect() {
            pageSizeSelect = document.querySelector('[data-page-size-select]');
            if (!pageSizeSelect) return;

            pageSizeSelect.addEventListener('change', function () {
                localStorage.setItem(STORAGE_KEY, pageSizeSelect.value);
                fetchList(buildParams({ page: '' }));
            });
        }

        bindPageSizeSelect();

        // --- Пагинация: перехват кликов ---

        function bindPaginationLinks() {
            // Ничего не нужно — используем делегирование
        }

        document.addEventListener('click', function (e) {
            var link = e.target.closest('[data-list-content] .pagination-link:not(.is-current):not(.is-disabled)');
            if (!link) return;

            e.preventDefault();
            var href = link.getAttribute('href');
            if (!href) return;

            var params = new URLSearchParams(href.split('?')[1] || '');
            fetchList(params);
        });

        // --- popstate ---

        function restoreFormFromParams(params) {
            if (searchInput) searchInput.value = params.get('q') || '';
            if (dateFromInput) dateFromInput.value = params.get('date_from') || '';
            if (dateToInput) dateToInput.value = params.get('date_to') || '';

            updateSearchState();
            syncCalendarVisibility();
        }

        window.addEventListener('popstate', function () {
            var params = new URLSearchParams(window.location.search);
            restoreFormFromParams(params);
            fetchList(params);
        });

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
