function initAutocomplete(selectId) {
    const select = document.getElementById(selectId);
    if (!select || select.dataset.acInitialized) return;
    select.dataset.acInitialized = '1';

    const searchUrl = select.dataset.searchUrl || '';
    const searchType = select.dataset.searchType || '';
    const isAjax = !!searchUrl;

    // ── DOM setup ─────────────────────────────────────────────────────────
    const container = document.createElement('div');
    container.style.cssText = 'position:relative; display:block;';
    container.className = 'autocomplete-container';

    const input = document.createElement('input');
    input.type = 'text';
    input.placeholder = isAjax ? 'Начните вводить для поиска…' : 'Начните вводить…';
    input.className = 'autocomplete-input';
    input.style.cssText = 'width:100%; padding-right:32px;';

    const clearBtn = document.createElement('button');
    clearBtn.type = 'button';
    clearBtn.className = 'autocomplete-clear';
    clearBtn.setAttribute('aria-label', 'Очистить');
    clearBtn.setAttribute('tabindex', '-1');
    clearBtn.textContent = '\u00d7';
    clearBtn.style.cssText = [
        'display:none; position:absolute; right:8px; top:50%; transform:translateY(-50%);',
        'border:none; background:none; cursor:pointer; font-size:1.2rem;',
        'color:#9ca3af; line-height:1; padding:2px 4px; border-radius:4px;',
        'transition:color .15s ease;',
    ].join('');

    const dropdown = document.createElement('div');
    dropdown.style.cssText = [
        'display:none; position:absolute; top:100%; left:0; right:0;',
        'max-height:220px; overflow-y:auto; background:#fff;',
        'border:1px solid #e5e7eb; border-top:none; border-radius:0 0 10px 10px;',
        'box-shadow:0 8px 16px rgba(15,23,42,.1); z-index:1100;',
    ].join('');
    dropdown.className = 'autocomplete-dropdown';

    select.parentNode.insertBefore(container, select);
    container.appendChild(input);
    container.appendChild(clearBtn);
    container.appendChild(dropdown);
    container.appendChild(select);

    // Скрываем оригинальный select, оставляем в DOM для отправки формы
    select.style.cssText = 'position:absolute; opacity:0; height:1px; width:1px; pointer-events:none; z-index:-1;';

    // ── Кнопка очистки ────────────────────────────────────────────────────
    function updateClearBtn() {
        clearBtn.style.display = select.value ? 'block' : 'none';
    }

    clearBtn.addEventListener('mousedown', function (e) {
        e.preventDefault();
        select.value = '';
        input.value = '';
        updateClearBtn();
        select.dispatchEvent(new Event('change', { bubbles: true }));
        input.focus();
    });

    clearBtn.addEventListener('mouseenter', function () { clearBtn.style.color = '#374151'; });
    clearBtn.addEventListener('mouseleave', function () { clearBtn.style.color = '#9ca3af'; });

    // ── Синхронизация начального значения ─────────────────────────────────
    var _inputInvalidating = false;

    function syncInputToSelect() {
        if (_inputInvalidating) return;
        if (select.value) {
            const opt = select.options[select.selectedIndex];
            input.value = opt ? opt.text : '';
        } else {
            input.value = '';
        }
        updateClearBtn();
    }
    select.addEventListener('change', syncInputToSelect);
    syncInputToSelect();

    // ── Рендер выпадающего списка ──────────────────────────────────────────
    function renderItems(items) {
        dropdown.innerHTML = '';
        if (!items.length) {
            dropdown.style.display = 'none';
            return;
        }
        items.forEach(function (item) {
            const el = document.createElement('div');
            el.textContent = item.text;
            el.style.cssText = 'padding:9px 12px; cursor:pointer; border-bottom:1px solid #f3f4f6; font-size:.92rem;';
            el.addEventListener('mouseenter', function () { this.style.background = '#f9fafb'; });
            el.addEventListener('mouseleave', function () { this.style.background = '#fff'; });
            el.addEventListener('mousedown', function (e) {
                e.preventDefault();
                selectItem(item);
            });
            dropdown.appendChild(el);
        });
        dropdown.style.display = 'block';
    }

    function selectItem(item) {
        // Добавляем опцию если её нет, затем устанавливаем значение
        let opt = Array.from(select.options).find(o => String(o.value) === String(item.id));
        if (!opt) {
            opt = new Option(item.text, item.id);
            select.add(opt);
        }
        select.value = item.id;
        input.value = item.text;
        dropdown.style.display = 'none';
        select.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function closeDropdown() {
        dropdown.style.display = 'none';
    }

    // ── AJAX-режим ────────────────────────────────────────────────────────
    if (isAjax) {
        let debounceTimer = null;
        let controller = null;

        function fetchResults(q) {
            if (controller) controller.abort();
            controller = new AbortController();

            const url = new URL(select.dataset.searchUrl || searchUrl, location.origin);
            if (q) url.searchParams.set('q', q);
            if (searchType) url.searchParams.set('type', searchType);

            fetch(url.toString(), { signal: controller.signal })
                .then(function (r) { return r.json(); })
                .then(function (data) { renderItems(data.results || []); })
                .catch(function () {});
        }

        input.addEventListener('focus', function () {
            if (select.dataset.openOnFocus === '1' && !input.value.trim()) fetchResults('');
        });

        input.addEventListener('input', function () {
            const q = input.value.trim();
            // Инвалидировать выбор если текст изменился
            if (select.value) {
                var selectedOpt = select.options[select.selectedIndex];
                if (!selectedOpt || selectedOpt.text !== q) {
                    _inputInvalidating = true;
                    select.value = '';
                    updateClearBtn();
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                    _inputInvalidating = false;
                }
            }
            if (!q) {
                if (select.dataset.openOnFocus === '1') {
                    fetchResults('');
                } else {
                    closeDropdown();
                }
                return;
            }
            if (q.length < 2) {
                closeDropdown();
                return;
            }
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function () { fetchResults(q); }, 300);
        });

    // ── DOM-режим (для quick_create модалки и обратной совместимости) ─────
    } else {
        function getDomItems(q) {
            const items = [];
            for (const opt of select.options) {
                if (!opt.value) continue;
                if (!q || opt.textContent.toLowerCase().includes(q.toLowerCase())) {
                    items.push({ id: opt.value, text: opt.text });
                }
            }
            return items;
        }

        input.addEventListener('input', function () {
            const q = input.value.trim();
            if (!q) {
                select.value = '';
                updateClearBtn();
                select.dispatchEvent(new Event('change', { bubbles: true }));
            }
            renderItems(getDomItems(q));
        });

        input.addEventListener('focus', function () {
            renderItems(getDomItems(input.value.trim()));
        });
    }

    // ── Общие обработчики ─────────────────────────────────────────────────
    input.addEventListener('blur', function () {
        setTimeout(function () {
            // Автовыбор единственного совпадения при уходе из поля
            if (!select.value && input.value.trim()) {
                var items = dropdown.querySelectorAll('div');
                if (items.length === 1) {
                    items[0].dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                }
            }
            closeDropdown();
        }, 200);
    });

    document.addEventListener('click', function (e) {
        if (!container.contains(e.target)) closeDropdown();
    });

    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const first = dropdown.querySelector('div');
            if (first) first.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
        }
        if (e.key === 'Escape') {
            closeDropdown();
            input.blur();
        }
    });
}

