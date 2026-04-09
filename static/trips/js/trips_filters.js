(function () {
    var STORAGE_KEY = 'tms_trips_page_size';
    var DEFAULT_PAGE_SIZE = '25';
    var DEFAULT_DATE_MODE = 'loading';

    function init() {
        var form = document.querySelector('[data-trip-filters]');
        if (!form) return;

        var pageSizeSelect = document.querySelector('[data-page-size-select]');
        var searchInput = form.querySelector('[data-search-input]');
        var searchClear = form.querySelector('[data-search-clear]');
        var resetBtn = form.querySelector('[data-filter="reset"]');
        var dateFromInput = form.querySelector('[data-filter="date_from"]');
        var dateToInput = form.querySelector('[data-filter="date_to"]');
        var quickDateButtons = form.querySelectorAll('[data-quick-date]');

        var fetchController = null;
        var debounceTimer = null;

        // Карта полей формы: name → { element, default }
        // Единый источник правды для buildParams / restoreFields
        var fields = [
            { name: 'q',                el: searchInput,                                    fallback: '' },
            { name: 'date_mode',        el: form.querySelector('[name="date_mode"]'),        fallback: DEFAULT_DATE_MODE },
            { name: 'date_from',        el: form.querySelector('[name="date_from"]'),        fallback: '' },
            { name: 'date_to',          el: form.querySelector('[name="date_to"]'),          fallback: '' },
            { name: 'contractor_role',  el: form.querySelector('[name="contractor_role"]'),  fallback: '' },
            { name: 'contractor_query', el: form.querySelector('[name="contractor_query"]'), fallback: '' },
        ];

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

        // --- Параметры ---

        function buildParams(overrides) {
            var params = new URLSearchParams();

            fields.forEach(function (f) {
                var val;
                if (overrides && f.name in overrides) {
                    val = overrides[f.name];
                } else if (f.el) {
                    val = f.el.value.trim();
                } else {
                    val = '';
                }
                if (val && val !== f.fallback) {
                    params.set(f.name, val);
                }
            });

            // page_size — из footer-select, только если не дефолт
            var ps;
            if (overrides && 'page_size' in overrides) {
                ps = overrides.page_size;
            } else if (pageSizeSelect) {
                ps = pageSizeSelect.value;
            }
            if (ps && String(ps) !== DEFAULT_PAGE_SIZE) {
                params.set('page_size', ps);
            }

            // page
            if (overrides && 'page' in overrides && overrides.page) {
                params.set('page', overrides.page);
            }

            return params;
        }

        function restoreFields(params) {
            fields.forEach(function (f) {
                if (f.el) {
                    f.el.value = params.get(f.name) || f.fallback;
                }
            });
            if (pageSizeSelect) {
                pageSizeSelect.value = params.get('page_size') || DEFAULT_PAGE_SIZE;
            }
            updateSearchState();
            updateQuickDateState();
        }

        // --- Fetch ---

        function fetchList(params, pushHistory) {
            var qs = params.toString();
            var urlStr = window.location.pathname + (qs ? '?' + qs : '');

            if (fetchController) fetchController.abort();
            fetchController = new AbortController();

            var tbody = document.querySelector('[data-trips-tbody]');
            if (tbody) tbody.style.opacity = '0.5';

            fetch(urlStr, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                signal: fetchController.signal,
            })
            .then(function (r) {
                if (r.status === 401 || r.status === 403) {
                    location.href = '/accounts/login/?next=' + encodeURIComponent(location.pathname);
                    return;
                }
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.text();
            })
            .then(function (html) {
                if (!html) return;

                var doc = new DOMParser().parseFromString(html, 'text/html');

                var newTbody = doc.querySelector('[data-trips-tbody]');
                var currentTbody = document.querySelector('[data-trips-tbody]');
                if (newTbody && currentTbody) {
                    currentTbody.innerHTML = newTbody.innerHTML;
                    currentTbody.style.opacity = '';
                }

                var paginationEl = doc.querySelector('[data-pagination-fragment]');
                var currentPagination = document.querySelector('[data-pagination-wrapper]');
                if (currentPagination) {
                    currentPagination.innerHTML = paginationEl ? paginationEl.innerHTML : '';
                }

                if (window.TmsTableColumns && window.TmsTableColumns.reinitRows) {
                    window.TmsTableColumns.reinitRows();
                }

                bindPageSizeSelect();

                if (pushHistory !== false) {
                    history.pushState(null, '', urlStr);
                }
            })
            .catch(function (err) {
                if (err.name === 'AbortError') return;
                var currentTbody = document.querySelector('[data-trips-tbody]');
                if (currentTbody) currentTbody.style.opacity = '';
                console.error('trips fetch error:', err);
            });
        }

        // --- Поиск ---

        function updateSearchState() {
            if (!searchInput) return;
            var hasValue = !!searchInput.value.trim();
            if (searchClear) searchClear.hidden = !hasValue;
            searchInput.classList.toggle('is-filtered', hasValue);
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

        // --- Форма (фильтры + submit) ---

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            fetchList(buildParams({ page: '' }));
        });

        // --- Быстрые даты ---

        function formatDate(date) {
            var year = date.getFullYear();
            var month = String(date.getMonth() + 1).padStart(2, '0');
            var day = String(date.getDate()).padStart(2, '0');
            return year + '-' + month + '-' + day;
        }

        function getShiftedDate(days) {
            var date = new Date();
            date.setHours(12, 0, 0, 0);
            date.setDate(date.getDate() + days);
            return formatDate(date);
        }

        function updateQuickDateState() {
            if (!dateFromInput || !dateToInput || !quickDateButtons.length) return;

            var fromValue = dateFromInput.value;
            var toValue = dateToInput.value;
            var yesterday = getShiftedDate(-1);
            var today = getShiftedDate(0);
            var tomorrow = getShiftedDate(1);
            var activeType = '';

            if (fromValue && toValue && fromValue === toValue) {
                if (fromValue === yesterday) activeType = 'yesterday';
                else if (fromValue === today) activeType = 'today';
                else if (fromValue === tomorrow) activeType = 'tomorrow';
            }

            quickDateButtons.forEach(function (button) {
                button.classList.toggle(
                    'is-active',
                    button.getAttribute('data-quick-date') === activeType
                );
            });
        }

        quickDateButtons.forEach(function (button) {
            button.addEventListener('click', function () {
                var type = button.getAttribute('data-quick-date');
                var value = '';
                if (type === 'yesterday') value = getShiftedDate(-1);
                else if (type === 'today') value = getShiftedDate(0);
                else if (type === 'tomorrow') value = getShiftedDate(1);

                if (dateFromInput) dateFromInput.value = value;
                if (dateToInput) dateToInput.value = value;

                updateQuickDateState();
                fetchList(buildParams({ page: '' }));
            });
        });

        if (dateFromInput) {
            dateFromInput.addEventListener('change', updateQuickDateState);
            dateFromInput.addEventListener('input', updateQuickDateState);
        }
        if (dateToInput) {
            dateToInput.addEventListener('change', updateQuickDateState);
            dateToInput.addEventListener('input', updateQuickDateState);
        }

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

        // --- Сброс ---

        if (resetBtn) {
            resetBtn.addEventListener('click', function () {
                // Очистить все поля формы
                fields.forEach(function (f) {
                    if (f.el) f.el.value = f.fallback;
                });
                if (searchInput) searchInput.value = '';
                updateSearchState();
                updateQuickDateState();
                fetchList(new URLSearchParams());
            });
        }

        // --- Пагинация: перехват кликов ---

        document.addEventListener('click', function (e) {
            var link = e.target.closest('[data-pagination-wrapper] a.pagination-link');
            if (!link) return;

            e.preventDefault();
            var href = link.getAttribute('href');
            if (!href) return;

            var params = new URLSearchParams(href.split('?')[1] || '');
            fetchList(params);
        });

        // --- popstate ---

        window.addEventListener('popstate', function () {
            var params = new URLSearchParams(window.location.search);
            restoreFields(params);
            fetchList(params, false);
        });

        updateSearchState();
        updateQuickDateState();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
