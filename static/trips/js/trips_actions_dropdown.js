// Открытие/закрытие dropdown "Действия", авто-открытие вверх при нехватке места
(function () {
    function init() {
        const dropdowns = document.querySelectorAll('[data-actions-dropdown]');
        if (!dropdowns.length) return;

        function closeAll() {
            dropdowns.forEach((dd) => {
                const menu = dd.querySelector('[data-actions-menu]');
                const btn = dd.querySelector('[data-actions-toggle]');
                if (!menu || !btn) return;
                menu.classList.remove('is-open', 'open-up');
                btn.setAttribute('aria-expanded', 'false');
            });
        }

        function shouldOpenUp(btn, menu) {
            menu.classList.remove('open-up');
            menu.classList.add('is-open');
            menu.style.visibility = 'hidden';

            const menuHeight = menu.offsetHeight;
            const btnRect = btn.getBoundingClientRect();
            const spaceBelow = window.innerHeight - btnRect.bottom;
            const spaceAbove = btnRect.top;

            menu.classList.remove('is-open');
            menu.style.visibility = '';

            return (spaceBelow < menuHeight + 12) && (spaceAbove > spaceBelow);
        }

        dropdowns.forEach((dd) => {
            const btn = dd.querySelector('[data-actions-toggle]');
            const menu = dd.querySelector('[data-actions-menu]');
            if (!btn || !menu) return;

            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                const isOpen = menu.classList.contains('is-open');
                closeAll();

                if (!isOpen) {
                    if (shouldOpenUp(btn, menu)) menu.classList.add('open-up');
                    else menu.classList.remove('open-up');

                    menu.classList.add('is-open');
                    btn.setAttribute('aria-expanded', 'true');
                }
            });

            menu.addEventListener('click', function (e) {
                e.stopPropagation();
            });
        });

        document.addEventListener('click', closeAll);
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closeAll();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();