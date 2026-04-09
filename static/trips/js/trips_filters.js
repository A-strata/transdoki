(function () {
    var STORAGE_KEY = 'tms_trips_page_size';
    var DEFAULT_PAGE_SIZE = '25';

    var CONTRACTOR_ROLES = ['driver', 'client', 'carrier'];

    var ROLE_LABELS = {
        driver: 'Водитель',
        client: 'Заказчик',
        carrier: 'Перевозчик'
    };


    function init() {
        var form = document.querySelector('[data-trip-filters]');
        if (!form) return;

        var searchInput = form.querySelector('[name="q"]');
        var calendarToggle = form.querySelector('[data-calendar-toggle]');
        var calendarFields = form.querySelector('[data-calendar-fields]');
        var dateFromInput = form.querySelector('[name="date_from"]');
        var dateToInput = form.querySelector('[name="date_to"]');
        var activeFiltersWrap = form.querySelector('[data-active-filters]');
        var searchWrap = searchInput ? searchInput.closest('.search-field-wrap') : null;
        var searchClear = form.querySelector('[data-search-clear]');
        var pageSizeSelect = document.querySelector('[data-page-size-select]');

        var fetchController = null;
        var debounceTimer = null;

        // Массив {role, value} — хранит порядок добавления фильтров.
        // Максимум один элемент на каждый role.
        var contractorFilterOrder = [];

        function getContractorValue(role) {
            for (var i = 0; i < contractorFilterOrder.length; i++) {
                if (contractorFilterOrder[i].role === role) return contractorFilterOrder[i].value;
            }
            return '';
        }

        function setContractorFilter(role, value) {
            var found = false;
            for (var i = 0; i < contractorFilterOrder.length; i++) {
                if (contractorFilterOrder[i].role === role) {
                    if (value) {
                        contractorFilterOrder[i].value = value;
                    } else {
                        contractorFilterOrder.splice(i, 1);
                    }
                    found = true;
                    break;
                }
            }
            if (!found && value) {
                contractorFilterOrder.push({ role: role, value: value });
            }
        }

        function removeContractorFilter(role) {
            contractorFilterOrder = contractorFilterOrder.filter(function (f) {
                return f.role !== role;
            });
        }

        // Восстановить contractor-фильтры из URL при загрузке
        var initParams = new URLSearchParams(window.location.search);
        CONTRACTOR_ROLES.forEach(function (role) {
            var val = initParams.get('contractor_' + role) || '';
            if (val) contractorFilterOrder.push({ role: role, value: val });
        });

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

            // Contractor-фильтры — каждый тип отдельным параметром
            contractorFilterOrder.forEach(function (f) {
                params.set('contractor_' + f.role, f.value);
            });

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

            var tbody = document.querySelector('[data-trips-tbody]');
            if (tbody) tbody.classList.add('is-loading');

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

                var doc = new DOMParser().parseFromString(html, 'text/html');

                var newTbody = doc.querySelector('[data-trips-tbody]');
                var currentTbody = document.querySelector('[data-trips-tbody]');
                if (newTbody && currentTbody) {
                    currentTbody.innerHTML = newTbody.innerHTML;
                    currentTbody.classList.remove('is-loading');
                }

                var paginationEl = doc.querySelector('[data-pagination-fragment]');
                var currentPagination = document.querySelector('[data-pagination-wrapper]');
                if (currentPagination) {
                    currentPagination.innerHTML = paginationEl ? paginationEl.innerHTML : '';
                }

                var newCount = doc.querySelector('[data-total-count]');
                var currentCount = document.querySelector('[data-total-count]');
                if (newCount && currentCount) {
                    currentCount.textContent = newCount.textContent;
                }

                if (window.TmsTableColumns && window.TmsTableColumns.reinitRows) {
                    window.TmsTableColumns.reinitRows();
                }

                bindPageSizeSelect();
                history.pushState(null, '', urlStr);
            })
            .catch(function (err) {
                if (err.name === 'AbortError') return;

                var container = document.querySelector('[data-trips-tbody]');
                if (container) {
                    container.classList.remove('is-loading');
                    if (err.message === 'server_error') {
                        container.innerHTML = '<tr><td colspan="24">' +
                            '<div class="alert alert-error">Произошла ошибка на сервере. ' +
                            '<button type="button" class="tms-btn tms-btn-secondary tms-btn-sm" ' +
                            'onclick="location.reload()">Обновить</button></div></td></tr>';
                    } else {
                        container.innerHTML = '<tr><td colspan="24">' +
                            '<div class="alert alert-error">Не удалось загрузить данные. ' +
                            '<button type="button" class="tms-btn tms-btn-secondary tms-btn-sm" ' +
                            'onclick="location.reload()">Обновить</button></div></td></tr>';
                    }
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

        // --- Чипы ---

        function createChip(type, text, modifier, onRemove) {
            var chip = document.createElement('span');
            chip.className = 'active-filter-chip ' + modifier;
            chip.setAttribute('data-chip', type);

            var textNode = document.createTextNode(text + ' ');
            chip.appendChild(textNode);

            var removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'chip-remove';
            removeBtn.setAttribute('aria-label', 'Сбросить фильтр');
            removeBtn.innerHTML = '<svg width="8" height="8" viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
                '<path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
            removeBtn.addEventListener('click', onRemove);

            chip.appendChild(removeBtn);
            return chip;
        }

        function hasAnyContractorFilter() {
            return contractorFilterOrder.length > 0;
        }

        function rebuildChips() {
            if (!activeFiltersWrap) return;
            activeFiltersWrap.innerHTML = '';

            // Чипы контрагентов — в порядке добавления
            contractorFilterOrder.forEach(function (f) {
                var label = ROLE_LABELS[f.role] || f.role;
                var chipText = label + ': ' + f.value;
                var chip = createChip('contractor_' + f.role, chipText, 'active-filter-chip--info', function () {
                    removeContractorFilter(f.role);
                    rebuildChips();
                    fetchList(buildParams({ page: '' }));
                });
                activeFiltersWrap.appendChild(chip);
            });
        }

        // --- Hover-иконки в таблице ---

        document.addEventListener('click', function (e) {
            var btn = e.target.closest('.cell-filter-btn');
            if (!btn) return;

            var td = btn.closest('[data-filterable]');
            if (!td) return;

            var role = td.getAttribute('data-filter-role');
            var value = td.getAttribute('data-filter-value');
            if (!role || !value) return;

            // Тот же тип — заменяет значение (на том же месте), другой — добавляется в конец
            setContractorFilter(role, value);

            rebuildChips();
            fetchList(buildParams({ page: '' }));
        });

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

        function restoreFormFromParams(params) {
            if (searchInput) searchInput.value = params.get('q') || '';
            if (dateFromInput) dateFromInput.value = params.get('date_from') || '';
            if (dateToInput) dateToInput.value = params.get('date_to') || '';

            contractorFilterOrder = [];
            CONTRACTOR_ROLES.forEach(function (role) {
                var val = params.get('contractor_' + role) || '';
                if (val) contractorFilterOrder.push({ role: role, value: val });
            });

            updateSearchState();
            syncCalendarVisibility();
            rebuildChips();
        }

        // Синхронизация видимости полей дат с их содержимым
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

        window.addEventListener('popstate', function () {
            var params = new URLSearchParams(window.location.search);
            restoreFormFromParams(params);
            fetchList(params);
        });

        // --- Инициализация ---

        updateSearchState();
        syncCalendarVisibility();

        if (hasAnyContractorFilter()) {
            rebuildChips();
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
