(function () {
    'use strict';

    var config = document.getElementById('qc-config');
    var endpoint = config ? config.dataset.addressSuggestUrl : '';
    if (!endpoint) return;

    function debounce(fn, delay) {
        var timer;
        return function () {
            var args = arguments;
            var ctx = this;
            clearTimeout(timer);
            timer = setTimeout(function () { fn.apply(ctx, args); }, delay);
        };
    }

    function initAddressSuggest(inputId) {
        var input = document.getElementById(inputId);
        if (!input) return;

        var wrapper = document.createElement('div');
        wrapper.className = 'address-suggest-wrap';
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        var list = document.createElement('div');
        list.className = 'address-suggest-list';
        wrapper.appendChild(list);

        var currentItems = [];
        var activeIndex = -1;
        var controller = null;

        function closeList() {
            list.style.display = 'none';
            list.innerHTML = '';
            currentItems = [];
            activeIndex = -1;
        }

        function render(items) {
            list.innerHTML = '';
            currentItems = items;
            activeIndex = -1;

            if (!items.length) {
                closeList();
                return;
            }

            items.forEach(function (item) {
                var el = document.createElement('div');
                el.className = 'address-suggest-item';
                el.textContent = item.value;
                el.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    input.value = item.value;
                    closeList();
                });
                list.appendChild(el);
            });

            list.style.display = 'block';
        }

        var loadSuggestions = debounce(function () {
            var q = input.value.trim();
            if (q.length < 3) {
                closeList();
                return;
            }

            if (controller) controller.abort();
            controller = new AbortController();

            fetch(endpoint + '?q=' + encodeURIComponent(q), { signal: controller.signal })
                .then(function (resp) {
                    if (!resp.ok) throw new Error('Request failed');
                    return resp.json();
                })
                .then(function (data) {
                    render(data && data.suggestions ? data.suggestions.slice(0, 5) : []);
                })
                .catch(function (e) {
                    if (e.name !== 'AbortError') closeList();
                });
        }, 300);

        input.addEventListener('input', loadSuggestions);

        input.addEventListener('keydown', function (e) {
            if (!currentItems.length) return;
            var nodes = list.querySelectorAll('.address-suggest-item');
            if (!nodes.length) return;

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                activeIndex = (activeIndex + 1) % nodes.length;
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                activeIndex = (activeIndex - 1 + nodes.length) % nodes.length;
            } else if (e.key === 'Enter' && activeIndex >= 0) {
                e.preventDefault();
                input.value = currentItems[activeIndex].value;
                closeList();
                return;
            } else if (e.key === 'Escape') {
                closeList();
                return;
            } else {
                return;
            }

            nodes.forEach(function (n, i) {
                n.classList.toggle('active', i === activeIndex);
            });
        });

        document.addEventListener('click', function (e) {
            if (!wrapper.contains(e.target)) closeList();
        });
    }

    initAddressSuggest('id_load-address');
    initAddressSuggest('id_unload-address');
})();
