/* Org switcher dropdown */
(function () {
    'use strict';

    function init() {
        const switcher = document.querySelector('.org-switcher');
        if (!switcher) return;

        const btn = switcher.querySelector('.org-switcher-btn');
        const dropdown = switcher.querySelector('.org-dropdown');
        if (!btn || !dropdown) return;

        function open() {
            document.dispatchEvent(new CustomEvent('tms:dropdown-open', { detail: { id: 'org-switcher' } }));
            btn.classList.add('is-open');
            dropdown.classList.add('is-open');
            btn.setAttribute('aria-expanded', 'true');
        }

        function close() {
            btn.classList.remove('is-open');
            dropdown.classList.remove('is-open');
            btn.setAttribute('aria-expanded', 'false');
        }

        function toggle() {
            if (dropdown.classList.contains('is-open')) {
                close();
            } else {
                open();
            }
        }

        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            toggle();
        });

        // Закрытие по клику вне
        document.addEventListener('click', function (e) {
            if (!switcher.contains(e.target)) {
                close();
            }
        });

        // Закрытие по Escape
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                close();
            }
        });

        // Закрытие при открытии другого дропдауна
        document.addEventListener('tms:dropdown-open', function (e) {
            if (e.detail.id !== 'org-switcher') close();
        });

        // Закрытие при клике по пункту меню
        dropdown.querySelectorAll('.org-dropdown-item').forEach(function (item) {
            item.addEventListener('click', function () {
                close();
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
