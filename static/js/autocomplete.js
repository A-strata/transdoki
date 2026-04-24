function initAutocomplete(selectId) {
    const select = document.getElementById(selectId);
    if (!select || select.dataset.acInitialized) return;
    select.dataset.acInitialized = '1';

    const searchUrl = select.dataset.searchUrl || '';
    const searchType = select.dataset.searchType || '';
    const isAjax = !!searchUrl;

    // ── Entity type + create (две ортогональные оси) ─────────────────────
    //
    // data-ac-entity-type=<organization|person|vehicle>
    //   Семантическое скоупинг поля: определяет тексты лейблов и
    //   empty-state из ENTITY_DEFAULTS. Задание entity-type включает
    //   empty-state: при пустых результатах показывается осмысленное
    //   сообщение (с объяснением причины, если надо). Без entity-type
    //   поведение как раньше — пустой дропдаун схлопывается молча.
    //
    // data-ac-create="1"
    //   Доступно ли inline-создание новой сущности прямо из дропдауна
    //   (футер «+ Добавить …», триггерящий quick_create.js-модалку).
    //   Полностью независим от entity-type в текущем состоянии. Может
    //   меняться динамически (см. trip_form_role.js: на поле активной
    //   роли create снимается, т.к. поле работает в режиме «только наши
    //   фирмы» и quick_create там создавал бы мусорный внешний контрагент).
    //
    // data-ac-create-label / data-ac-create-empty
    //   Пер-поле оверрайды дефолтных текстов (label футера и empty-state
    //   при доступном create). Редко нужны — основной путь через
    //   ENTITY_DEFAULTS.
    //
    // data-ac-qc-<suffix>="value"
    //   Прокидываются на proxy-кнопку quick_create как data-qc-<suffix>.
    //   Пример: data-ac-qc-vehicle-types="single,truck" → data-qc-vehicle-types,
    //   которое quick_create.js использует для фильтрации типов ТС.
    //
    // Тексты:
    //   empty          — когда создание доступно (над футером «+ Добавить»).
    //                    Призыв «…либо добавьте новую» уместен.
    //   emptyNoCreate  — когда создание недоступно (либо не включено, либо
    //                    снято рантайм-логикой активной роли). Без призыва
    //                    к созданию; для organization — объяснение
    //                    ограничения «только наши фирмы».
    const ENTITY_DEFAULTS = {
        organization: {
            label: 'Добавить организацию',
            empty: 'Организация не найдена в справочнике. Проверьте написание — либо добавьте новую.',
            emptyNoCreate: 'Совпадений среди ваших фирм нет. Добавить свою фирму можно только в личном кабинете.',
        },
        person: {
            label: 'Добавить водителя',
            empty: 'Водитель не найден в справочнике. Проверьте написание — либо добавьте нового.',
            emptyNoCreate: 'Совпадений не найдено. Проверьте написание.',
        },
        vehicle: {
            label: 'Добавить ТС',
            empty: 'Запись не найдена в справочнике. Проверьте написание — либо добавьте новую.',
            emptyNoCreate: 'Совпадений не найдено. Проверьте написание.',
        },
    };
    const GENERIC_DEFAULTS = {
        label: 'Добавить',
        empty: 'Ничего не найдено.',
        emptyNoCreate: 'Ничего не найдено.',
    };

    const entityType = select.dataset.acEntityType || '';
    const entityDefaults = ENTITY_DEFAULTS[entityType] || GENERIC_DEFAULTS;
    const createLabel = select.dataset.acCreateLabel || entityDefaults.label;
    const createEmptyMsg = select.dataset.acCreateEmpty || entityDefaults.empty;
    const createEmptyMsgNoCreate = entityDefaults.emptyNoCreate;

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
        'display:none; position:fixed;',
        'max-height:220px; overflow-y:auto; background:#fff;',
        'border:1px solid #e5e7eb; border-radius:0 0 10px 10px;',
        'box-shadow:0 8px 16px rgba(15,23,42,.1); z-index:1100;',
    ].join('');
    dropdown.className = 'autocomplete-dropdown';
    dropdown.setAttribute('data-ac-for', selectId);

    select.parentNode.insertBefore(container, select);
    container.appendChild(input);
    container.appendChild(clearBtn);
    container.appendChild(select);
    document.body.appendChild(dropdown);

    // Скрываем оригинальный select, оставляем в DOM для отправки формы
    select.style.cssText = 'position:absolute; opacity:0; height:1px; width:1px; pointer-events:none; z-index:-1;';

    // ── Позиционирование dropdown в body ──────────────────────────────────
    function getScrollParent(el) {
        var node = el.parentElement;
        while (node && node !== document.body) {
            if (/(auto|scroll)/.test(getComputedStyle(node).overflowY)) return node;
            node = node.parentElement;
        }
        return null;
    }

    var scrollParent = null;
    var rafId = null;
    // Фактическая высота контента dropdown'а. Обновляется в
    // measureContentHeight() при каждом рендере списка. Используется
    // в positionDropdown() вместо preferredH, чтобы решение о флипе
    // принималось по реальному размеру dropdown'а, а не по резервному
    // максимуму. Без этого короткий dropdown (например, empty-state
    // «не найдено» + футер «+ Добавить») мог уходить вверх только
    // потому, что снизу оставалось меньше preferredH — хотя для двух
    // строк места было с запасом.
    var cachedContentH = 0;

    function getVisibleTop() {
        var top = 0;
        var header = document.querySelector('.nav-wrap');
        if (header) top = header.getBoundingClientRect().bottom;
        var sticky = input.closest('form');
        if (sticky) {
            var nav = sticky.querySelector('.sticky-nav');
            if (nav) {
                var nb = nav.getBoundingClientRect().bottom;
                if (nb > top) top = nb;
            }
        }
        return top;
    }

    // Замер естественной высоты dropdown'а. Снимаем max-height, ставим
    // display:block + visibility:hidden (изменение и восстановление
    // синхронны в одном tick'е — пользователь ничего не видит), читаем
    // offsetHeight. Ширину фиксируем заранее — иначе при auto-width
    // перенос строк исказит высоту. Вызывается из renderResponse
    // каждый раз, когда содержимое меняется; scroll-reposition читает
    // кэшированное значение и не пере-замеряет.
    function measureContentHeight() {
        var rect = input.getBoundingClientRect();
        dropdown.style.width = rect.width + 'px';
        var prevDisplay = dropdown.style.display;
        var prevVisibility = dropdown.style.visibility;
        dropdown.style.maxHeight = 'none';
        dropdown.style.visibility = 'hidden';
        dropdown.style.display = 'block';
        cachedContentH = dropdown.offsetHeight;
        dropdown.style.display = prevDisplay;
        dropdown.style.visibility = prevVisibility;
    }

    function positionDropdown() {
        var rect = input.getBoundingClientRect();
        var visibleTop = getVisibleTop();
        // Prefer-fit: если desiredH помещается снизу — открываем вниз на
        // полную высоту. Если снизу не помещается, а сверху есть место —
        // флипаем наверх (без фазы «сжатия»). Если не помещается ни
        // вниз, ни вверх — выбираем сторону с большим запасом, внутренний
        // скролл остаётся как fallback.
        //
        // desiredH = min(preferredH, cachedContentH): для коротких
        // dropdown'ов (empty-state + footer) порог флипа становится
        // низким и не срабатывает зря. Для длинных — всё как раньше,
        // эффективно равно preferredH.
        //
        // Гистерезис (flipHysteresis) нужен, чтобы при медленной прокрутке
        // dropdown не дребезжал вверх-вниз на границе: единожды флипнув,
        // требуем заметного перевеса другой стороны для обратного флипа.
        var viewportPad = 8;
        var preferredH = 220;
        var flipHysteresis = 40;
        var desiredH = Math.min(preferredH, cachedContentH || preferredH);

        var spaceBelow = window.innerHeight - rect.bottom - viewportPad;
        var spaceAbove = rect.top - visibleTop - viewportPad;

        var wasUp = dropdown.dataset.acDir === 'up';
        var openUp;
        if (wasUp) {
            // Держим текущее направление, пока снизу не станет заметно лучше.
            openUp = spaceBelow < desiredH && spaceAbove + flipHysteresis > spaceBelow;
        } else {
            openUp = spaceBelow < desiredH && spaceAbove > spaceBelow + flipHysteresis;
        }

        var available = openUp ? spaceAbove : spaceBelow;
        var maxH = Math.max(80, Math.min(desiredH, available));
        dropdown.style.maxHeight = maxH + 'px';

        dropdown.style.left = rect.left + 'px';
        dropdown.style.width = rect.width + 'px';

        if (openUp) {
            dropdown.dataset.acDir = 'up';
            dropdown.style.top = 'auto';
            dropdown.style.bottom = (window.innerHeight - rect.top) + 'px';
            dropdown.style.borderRadius = '10px 10px 0 0';
        } else {
            dropdown.dataset.acDir = 'down';
            dropdown.style.top = rect.bottom + 'px';
            dropdown.style.bottom = 'auto';
            dropdown.style.borderRadius = '0 0 10px 10px';
        }
    }

    function onScrollReposition() {
        if (dropdown.style.display === 'none') return;
        if (rafId) cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(function () {
            var rect = input.getBoundingClientRect();
            var visibleTop = getVisibleTop();
            if (rect.top < visibleTop || rect.top > window.innerHeight) {
                closeDropdown();
            } else {
                positionDropdown();
            }
        });
    }

    function attachScrollListener() {
        if (!scrollParent) scrollParent = getScrollParent(input);
        if (scrollParent) {
            scrollParent.addEventListener('scroll', onScrollReposition, { passive: true });
        }
        window.addEventListener('scroll', onScrollReposition, { passive: true });
    }

    function detachScrollListener() {
        if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
        if (scrollParent) {
            scrollParent.removeEventListener('scroll', onScrollReposition);
        }
        window.removeEventListener('scroll', onScrollReposition);
    }

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

    // form.reset() не вызывает change на select — слушаем reset отдельно
    var parentForm = select.closest('form');
    if (parentForm) {
        parentForm.addEventListener('reset', function () {
            setTimeout(syncInputToSelect, 0);
        });
    }

    // ── Рендер выпадающего списка ──────────────────────────────────────────
    function createItemEl(item, muted) {
        var el = document.createElement('div');
        el.textContent = item.text;
        el.style.cssText = 'padding:9px 12px; cursor:pointer; border-bottom:1px solid #f3f4f6; font-size:.92rem;';
        if (muted) el.style.color = 'var(--muted)';
        el.addEventListener('mouseenter', function () { this.style.background = '#f9fafb'; });
        el.addEventListener('mouseleave', function () { this.style.background = '#fff'; });
        el.addEventListener('mousedown', function (e) {
            e.preventDefault();
            selectItem(item);
        });
        return el;
    }

    function createGroupHeader(text) {
        var el = document.createElement('div');
        el.textContent = text;
        el.style.cssText = 'padding:6px 12px; font-size:var(--text-xs); font-weight:600; color:var(--muted); text-transform:uppercase; letter-spacing:.03em;';
        return el;
    }

    function createHintEl(text, type) {
        var el = document.createElement('div');
        el.textContent = text;
        // type: 'warning' | 'info'. По умолчанию — warning (жёлтая плашка),
        // info — нейтральная. Цвета берутся из тех же CSS-переменных, что
        // и на остальных предупреждениях приложения.
        var isInfo = type === 'info';
        var colorVars = isInfo
            ? 'color:var(--muted); background:var(--hover-active); border-bottom:1px solid var(--border);'
            : 'color:var(--warning-text); background:var(--warning-bg); border-bottom:1px solid var(--warning-border);';
        el.style.cssText = 'padding:8px 12px; font-size:var(--text-sm); ' + colorVars;
        return el;
    }

    // ── Inline-create footer (пункт «+ Добавить …» внизу dropdown) ─────────
    function createCreateFooterEl() {
        var el = document.createElement('div');
        el.className = 'autocomplete-create-footer';
        el.setAttribute('data-ac-role', 'create');
        el.setAttribute('role', 'option');
        el.style.cssText = [
            'padding:10px 12px; cursor:pointer; font-size:.92rem;',
            'color:var(--primary); font-weight:600; background:var(--hover-active);',
            'border-top:1px solid var(--border);',
            'display:flex; align-items:center; gap:8px;',
        ].join('');
        var plus = document.createElement('span');
        plus.textContent = '+';
        plus.style.cssText = 'font-size:1.05rem; line-height:1;';
        var label = document.createElement('span');
        label.textContent = createLabel;
        el.appendChild(plus);
        el.appendChild(label);
        el.addEventListener('mouseenter', function () { this.style.background = 'var(--primary)'; this.style.color = '#fff'; });
        el.addEventListener('mouseleave', function () { this.style.background = 'var(--hover-active)'; this.style.color = 'var(--primary)'; });
        el.addEventListener('mousedown', function (e) {
            e.preventDefault();
            triggerQuickCreate();
        });
        return el;
    }

    function createEmptyStateEl(text) {
        var el = document.createElement('div');
        el.className = 'autocomplete-empty-state';
        el.setAttribute('data-ac-role', 'empty');
        el.textContent = text || createEmptyMsg;
        el.style.cssText = [
            'padding:12px 14px; font-size:var(--text-sm);',
            'color:var(--muted); line-height:1.45;',
        ].join('');
        return el;
    }

    function triggerQuickCreate() {
        // Очищаем содержимое dropdown — иначе отложенный blur-автовыбор
        // (см. обработчик blur ниже) через 200ms может выбрать единственный
        // оставшийся real-item, хотя пользователь явно кликнул «Добавить».
        dropdown.innerHTML = '';
        closeDropdown();
        // Делегируем quick_create.js: он слушает клики по [data-qc-type]
        // глобально. Создаём временный элемент с нужными атрибутами и
        // диспатчим на нём click, чтобы не дублировать логику открытия модалки.
        var proxy = document.createElement('button');
        proxy.type = 'button';
        proxy.dataset.qcType = entityType;
        proxy.dataset.qcTarget = select.id;
        // Пробрасываем доп. атрибуты для quick_create: data-ac-qc-<name>
        // на <select> превращаются в data-qc-<name> на proxy. Например,
        // data-ac-qc-vehicle-types="single,truck" → data-qc-vehicle-types.
        // dataset хранит ключи в camelCase: acQcVehicleTypes → qcVehicleTypes.
        Object.keys(select.dataset).forEach(function (key) {
            if (key.length > 4 && key.indexOf('acQc') === 0) {
                proxy.dataset['qc' + key.slice(4)] = select.dataset[key];
            }
        });
        proxy.style.display = 'none';
        document.body.appendChild(proxy);
        proxy.click();
        document.body.removeChild(proxy);
    }

    function appendCreateFooter() {
        // Без entityType футер показать нельзя — quick_create.js не знает,
        // какую модалку открывать. Гарантируется дополнительно внешним
        // гейтом canShowCreate в renderResponse.
        if (!entityType) return;
        dropdown.appendChild(createCreateFooterEl());
    }

    // Единый рендер ответа search-endpoint'а.
    //
    // Формат ответа (см. transdoki/search.py):
    //   {
    //     items:   [{id, text, group?}, ...],
    //     groups?: [{key, label}, ...],
    //     hint?:   {type, text}
    //   }
    //
    // - Если groups отсутствует/пусто → items рендерятся плоско.
    // - Если groups задана → элементы разбиваются по item.group в порядке
    //   groups; заголовок группы выводится только если label задан и это
    //   не первая отрисованная группа (первая безымянная — без заголовка).
    // - hint — одна подсказка над списком (warning/info).
    // - Combobox-футер «+ Добавить …» и empty-state работают одинаково
    //   для всех полей (нет двух веток кода, которые могут рассинхрониться).
    function renderResponse(data) {
        dropdown.innerHTML = '';
        var items = (data && data.items) || [];
        var groups = (data && data.groups) || null;
        var hint = (data && data.hint) || null;
        var q = input.value.trim();
        // Две ортогональные оси:
        //   entityType     — есть ли у поля семантика (organization/person/
        //                    vehicle). Включает empty-state и даёт тексты.
        //   createAllowed  — предлагать ли inline-создание (футер). Читается
        //                    из data-ac-create на каждом рендере, так что
        //                    рантайм-переключения (trip_form_role.js на
        //                    поле активной роли) подхватываются мгновенно.
        // canShowEmptyState шире canShowCreate: пустое состояние остаётся
        // информативным, даже когда создание выключено.
        var createAllowed = select.dataset.acCreate === '1';
        var canShowCreate = createAllowed && !!entityType && q.length >= 2;
        var canShowEmptyState = !!entityType && q.length >= 2;

        if (!items.length && !canShowEmptyState) {
            dropdown.style.display = 'none';
            detachScrollListener();
            return;
        }

        if (hint && hint.text) {
            dropdown.appendChild(createHintEl(hint.text, hint.type || 'warning'));
        }

        if (items.length) {
            if (groups && groups.length) {
                // Разложить items по группам, сохранив порядок внутри группы.
                var buckets = {};
                groups.forEach(function (g) { buckets[g.key] = []; });
                items.forEach(function (it) {
                    var bucket = it.group && buckets[it.group];
                    if (bucket) bucket.push(it);
                });

                var rendered = 0;
                groups.forEach(function (g) {
                    var bucket = buckets[g.key] || [];
                    if (!bucket.length) return;
                    // Заголовок рисуем только когда уже что-то отрисовано выше,
                    // и только если у группы есть человекочитаемый label.
                    if (rendered > 0 && g.label) {
                        dropdown.appendChild(createGroupHeader(g.label));
                    }
                    bucket.forEach(function (it) {
                        // muted=true для элементов «не в первой группе» —
                        // сохраняет прежнее визуальное разделение
                        // (carrier-записи ярче, others — приглушённее).
                        dropdown.appendChild(createItemEl(it, rendered > 0));
                    });
                    rendered += bucket.length;
                });
            } else {
                items.forEach(function (it) {
                    dropdown.appendChild(createItemEl(it, false));
                });
            }
            if (canShowCreate) appendCreateFooter();
        } else {
            // items пусто. Текст empty-state — линейный выбор по
            // createAllowed: с призывом «добавьте новую» или без.
            // Футер рисуем только если создание реально доступно.
            var emptyText = createAllowed ? createEmptyMsg : createEmptyMsgNoCreate;
            dropdown.appendChild(createEmptyStateEl(emptyText));
            if (canShowCreate) appendCreateFooter();
        }

        // Замеряем реальную высоту контента до позиционирования —
        // positionDropdown() использует её для принятия решения о флипе.
        measureContentHeight();
        positionDropdown();
        dropdown.style.display = 'block';
        attachScrollListener();
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
        closeDropdown();
        select.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function closeDropdown() {
        dropdown.style.display = 'none';
        detachScrollListener();
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
                .then(renderResponse)
                .catch(function () {});
        }

        input.addEventListener('focus', function () {
            // openOnFocusAlways='1' — открывать дропдаун на фокус всегда,
            // даже если поле уже заполнено (для полей с коротким списком
            // вариантов, например «моя фирма» при активной карточке роли).
            // openOnFocus='1' — только если поле пустое (старая семантика).
            if (select.dataset.openOnFocusAlways === '1') {
                fetchResults('');
            } else if (select.dataset.openOnFocus === '1' && !input.value.trim()) {
                fetchResults('');
            }
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
                // Отменяем отложенный и in-flight запрос: иначе результаты
                // для предыдущей строки (например от последнего нажатия перед
                // полной очисткой) придут и нарисуют dropdown на пустом поле.
                clearTimeout(debounceTimer);
                if (controller) controller.abort();
                if (select.dataset.openOnFocus === '1') {
                    fetchResults('');
                } else {
                    closeDropdown();
                }
                return;
            }
            if (q.length < 2) {
                clearTimeout(debounceTimer);
                if (controller) controller.abort();
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
            // DOM-режим оборачивает список из <option> в тот же контракт,
            // что и AJAX-ответ, — renderResponse работает единообразно.
            renderResponse({ items: getDomItems(q) });
        });

        input.addEventListener('focus', function () {
            renderResponse({ items: getDomItems(input.value.trim()) });
        });
    }

    // ── Общие обработчики ─────────────────────────────────────────────────
    input.addEventListener('blur', function () {
        setTimeout(function () {
            // Автовыбор единственного совпадения при уходе из поля.
            // Считаем только "настоящие" items (без data-ac-role) — empty-state
            // и create-footer не должны автовыбираться по blur.
            if (!select.value && input.value.trim()) {
                var items = dropdown.querySelectorAll('div:not([data-ac-role])');
                if (items.length === 1) {
                    items[0].dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                }
            }
            closeDropdown();
        }, 200);
    });

    document.addEventListener('click', function (e) {
        if (!container.contains(e.target) && !dropdown.contains(e.target)) closeDropdown();
    });

    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            // Сначала ищем обычный item, затем — create-footer (когда
            // совпадений нет и единственное действие — создать).
            var first = dropdown.querySelector('div:not([data-ac-role])')
                || dropdown.querySelector('[data-ac-role="create"]');
            if (first) first.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
        }
        if (e.key === 'Escape') {
            closeDropdown();
            input.blur();
        }
    });
}

