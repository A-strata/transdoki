(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var nav = document.getElementById('sticky-nav');
        if (!nav) return;

        var links = nav.querySelectorAll('.sticky-nav-link[data-nav-target]');
        if (!links.length) return;

        var SCROLL_KEYS = new Set(['Space', 'PageUp', 'PageDown', 'End', 'Home', 'ArrowUp', 'ArrowDown']);

        function clearActive() {
            links.forEach(function (l) { l.classList.remove('is-active'); });
        }

        // Клик → подсветка + smooth scroll
        links.forEach(function (link) {
            link.addEventListener('click', function () {
                var section = document.getElementById(link.dataset.navTarget);
                if (!section) return;
                clearActive();
                link.classList.add('is-active');
                section.scrollIntoView({ behavior: 'smooth' });
            });
        });

        // Пользовательский скролл → сброс подсветки
        window.addEventListener('wheel', clearActive, { passive: true });
        window.addEventListener('touchmove', clearActive, { passive: true });
        window.addEventListener('keydown', function (e) {
            if (SCROLL_KEYS.has(e.key)) clearActive();
        });
    });
})();
