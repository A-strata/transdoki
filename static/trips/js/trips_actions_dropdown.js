// Dropdown "Документы" в строках таблицы рейсов:
// - открывается по клику на иконку принтера
// - закрывается по клику вне, Escape, скроллу таблицы
(function () {
    function init() {
        let openMenu = null;

        function closeAll() {
            if (!openMenu) return;

            openMenu.menu.classList.remove('is-open');
            openMenu.btn.setAttribute('aria-expanded', 'false');
            openMenu = null;
        }

        document.addEventListener('click', function (e) {
            const toggle = e.target.closest('[data-docs-toggle]');

            if (toggle) {
                e.preventDefault();
                e.stopPropagation();

                const dropdown = toggle.closest('[data-docs-dropdown]');
                const menu = dropdown ? dropdown.querySelector('[data-docs-menu]') : null;
                if (!menu) return;

                const wasOpen = menu.classList.contains('is-open');
                closeAll();

                if (!wasOpen) {
                    document.dispatchEvent(new CustomEvent('tms:dropdown-open', { detail: { id: 'docs-menu' } }));
                    menu.classList.add('is-open');
                    toggle.setAttribute('aria-expanded', 'true');
                    openMenu = { menu: menu, btn: toggle };
                }

                return;
            }

            if (openMenu && !openMenu.menu.contains(e.target)) {
                closeAll();
            }
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closeAll();
        });

        document.addEventListener('tms:dropdown-open', function (e) {
            if (e.detail.id !== 'docs-menu') closeAll();
        });

        document.addEventListener('tms:drag-scroll-start', closeAll);

        var tableWrap = document.querySelector('[data-drag-scroll]');
        if (tableWrap) {
            tableWrap.addEventListener('scroll', closeAll);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
