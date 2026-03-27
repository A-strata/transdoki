/**
 * Поиск организации по названию или ИНН на странице регистрации.
 * Три состояния: search → selected → manual.
 */
(function () {
    var searchField  = document.getElementById('org-search-field');
    var searchInput  = document.getElementById('org-search');
    var selectedRow  = document.getElementById('org-selected-row');
    var selectedText = document.getElementById('org-selected-text');
    var changeBtn    = document.getElementById('org-change-btn');
    var manualBlock  = document.getElementById('org-manual-block');
    var manualLink   = document.getElementById('org-manual-link');
    var backLink     = document.getElementById('org-back-link');
    var nameInput    = document.getElementById('org-name-input');
    var innInput     = document.getElementById('org-inn-input');
    var hiddenInn       = document.getElementById('id_inn');
    var hiddenShortName = document.getElementById('id_short_name');
    var hiddenFullName  = document.getElementById('id_full_name');
    var hiddenKpp       = document.getElementById('id_kpp');
    var hiddenOgrn      = document.getElementById('id_ogrn');
    var hiddenAddress   = document.getElementById('id_address');
    var spin     = document.getElementById('org-spin');
    var dropdown = document.getElementById('org-dropdown');

    if (!searchInput || !hiddenInn || !hiddenShortName) return;

    var suggestUrl = searchInput.dataset.suggestUrl || '/organizations/api/party_suggest/';
    var timer      = null;
    var activeIndex = -1;

    /* ---------- состояния ---------- */

    function setState(state) {
        searchField.classList.toggle('org-hidden', state !== 'search');
        selectedRow.classList.toggle('org-visible', state === 'selected');
        manualBlock.classList.toggle('org-visible', state === 'manual');
    }

    function clearHiddenFields() {
        hiddenInn.value       = '';
        hiddenShortName.value = '';
        hiddenFullName.value  = '';
        if (hiddenKpp)     hiddenKpp.value     = '';
        if (hiddenOgrn)    hiddenOgrn.value    = '';
        if (hiddenAddress) hiddenAddress.value = '';
    }

    /* ---------- дропдаун ---------- */

    function getItems() {
        return dropdown.querySelectorAll('.org-suggestion-item');
    }

    function setActive(index) {
        var items = getItems();
        items.forEach(function (el) { el.classList.remove('is-active'); });
        activeIndex = index;
        if (index >= 0 && index < items.length) {
            items[index].classList.add('is-active');
            items[index].scrollIntoView({ block: 'nearest' });
        }
    }

    function showDropdown(suggestions) {
        dropdown.innerHTML = '';
        activeIndex = -1;
        if (!suggestions || !suggestions.length) {
            dropdown.classList.remove('visible');
            return;
        }
        suggestions.forEach(function (item, i) {
            var li = document.createElement('li');
            li.className = 'org-suggestion-item';
            li.setAttribute('role', 'option');

            var nameSpan = document.createElement('span');
            nameSpan.className = 'sug-name';
            nameSpan.textContent = item.short_name || item.full_name || '';

            var innSpan = document.createElement('span');
            innSpan.className = 'sug-inn';
            innSpan.textContent = 'ИНН\u00a0' + item.inn;

            li.appendChild(nameSpan);
            li.appendChild(innSpan);
            li.addEventListener('mouseenter', function () { setActive(i); });
            li.addEventListener('mousedown', function (e) {
                e.preventDefault();
                selectSuggestion(item);
            });
            dropdown.appendChild(li);
        });
        dropdown.classList.add('visible');
    }

    function hideDropdown() {
        dropdown.classList.remove('visible');
        dropdown.innerHTML = '';
        activeIndex = -1;
    }

    /* ---------- выбор ---------- */

    function selectSuggestion(item) {
        var shortName = item.short_name || item.full_name || '';
        hiddenInn.value       = item.inn;
        hiddenShortName.value = shortName;
        hiddenFullName.value  = item.full_name || shortName;
        if (hiddenKpp)     hiddenKpp.value     = item.kpp     || '';
        if (hiddenOgrn)    hiddenOgrn.value    = item.ogrn    || '';
        if (hiddenAddress) hiddenAddress.value = item.address || '';
        selectedText.textContent = shortName + '\u00a0·\u00a0ИНН\u00a0' + item.inn;
        hideDropdown();
        clearTimeout(timer);
        if (spin) spin.classList.remove('active');
        setState('selected');
    }

    function clearSelection() {
        clearHiddenFields();
        searchInput.value = '';
        selectedRow.classList.remove('org-error');
        hideDropdown();
        setState('search');
        searchInput.focus();
    }

    /* ---------- поисковый инпут ---------- */

    searchInput.addEventListener('input', function () {
        var q = this.value.trim();
        clearTimeout(timer);
        if (spin) spin.classList.remove('active');
        hideDropdown();

        if (q.length < 3) return;

        if (spin) spin.classList.add('active');
        timer = setTimeout(function () {
            fetch(suggestUrl + '?q=' + encodeURIComponent(q))
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (data) {
                    if (spin) spin.classList.remove('active');
                    showDropdown(data && data.suggestions);
                })
                .catch(function () {
                    if (spin) spin.classList.remove('active');
                    hideDropdown();
                });
        }, 400);
    });

    searchInput.addEventListener('keydown', function (e) {
        if (!dropdown.classList.contains('visible')) return;
        var items = getItems();
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setActive(Math.min(activeIndex + 1, items.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActive(Math.max(activeIndex - 1, 0));
        } else if (e.key === 'Enter') {
            if (activeIndex >= 0 && items[activeIndex]) {
                e.preventDefault();
                items[activeIndex].dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
            }
        } else if (e.key === 'Escape') {
            hideDropdown();
        }
    });

    searchInput.addEventListener('blur', function () {
        setTimeout(hideDropdown, 150);
    });

    /* ---------- кнопки управления ---------- */

    changeBtn.addEventListener('click', clearSelection);

    if (manualLink) {
        manualLink.addEventListener('click', function (e) {
            e.preventDefault();
            clearHiddenFields();
            if (nameInput) nameInput.value = '';
            if (innInput)  innInput.value  = '';
            setState('manual');
            if (nameInput) nameInput.focus();
        });
    }

    if (backLink) {
        backLink.addEventListener('click', function (e) {
            e.preventDefault();
            clearHiddenFields();
            setState('search');
            searchInput.focus();
        });
    }

    /* ---------- ручной ввод → скрытые поля ---------- */

    if (nameInput) {
        nameInput.addEventListener('input', function () {
            hiddenShortName.value = this.value;
            hiddenFullName.value  = this.value;
        });
    }

    if (innInput) {
        innInput.addEventListener('input', function () {
            var raw = this.value.replace(/\D/g, '');
            if (this.value !== raw) this.value = raw;
            hiddenInn.value = raw;
        });
    }

    /* ---------- инициализация при перерендере формы ---------- */

    if (hiddenInn.value && hiddenShortName.value) {
        selectedText.textContent = hiddenShortName.value + '\u00a0·\u00a0ИНН\u00a0' + hiddenInn.value;
        setState('selected');
        if (document.querySelector('.org-field-errors')) {
            selectedRow.classList.add('org-error');
        }
    } else if (hiddenInn.value || hiddenShortName.value) {
        if (nameInput) nameInput.value = hiddenShortName.value;
        if (innInput)  innInput.value  = hiddenInn.value;
        setState('manual');
    }
})();
