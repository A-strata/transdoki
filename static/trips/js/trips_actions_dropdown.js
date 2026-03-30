// Dropdown "Действия":
// - меню переносится в body
// - не обрезается таблицей
// - открывается возле кнопки
// - закрывается, если кнопка вышла из видимой области таблицы
// - подсвечивает строку с открытым меню
(function () {
    function init() {
        const dropdowns = document.querySelectorAll('[data-actions-dropdown]');
        if (!dropdowns.length) return;

        let openState = null;

        function setRowHighlight(dd, active) {
            const row = dd ? dd.closest('tr[data-trip-row]') : null;
            if (!row) return;

            row.classList.toggle('is-dropdown-open', !!active);
        }

        function closeAll() {
            dropdowns.forEach((dd) => {
                const menu = dd.querySelector('[data-actions-menu]') || document.querySelector(`[data-actions-menu-owner="${dd.dataset.dropdownId}"]`);
                const btn = dd.querySelector('[data-actions-toggle]');
                if (!menu || !btn) return;

                menu.classList.remove('is-open');
                menu.style.top = '';
                menu.style.left = '';
                menu.style.visibility = '';

                // Возвращаем меню обратно в dropdown
                if (menu.__placeholder && menu.__placeholder.parentNode) {
                    menu.__placeholder.parentNode.insertBefore(menu, menu.__placeholder);
                    menu.__placeholder.remove();
                    menu.__placeholder = null;
                }

                btn.setAttribute('aria-expanded', 'false');
                setRowHighlight(dd, false);
            });

            openState = null;
        }

        function isButtonVisibleInTableWrap(btn) {
            const wrap = document.querySelector('[data-drag-scroll]');
            if (!wrap) return true;

            const btnRect = btn.getBoundingClientRect();
            const wrapRect = wrap.getBoundingClientRect();

            const verticallyVisible =
                btnRect.bottom > wrapRect.top &&
                btnRect.top < wrapRect.bottom;

            const horizontallyVisible =
                btnRect.right > wrapRect.left &&
                btnRect.left < wrapRect.right;

            return verticallyVisible && horizontallyVisible;
        }

        function placeMenu(btn, menu) {
            menu.style.visibility = 'hidden';
            menu.classList.add('is-open');

            const btnRect = btn.getBoundingClientRect();
            const menuRect = menu.getBoundingClientRect();
            const gap = 6;

            let top = btnRect.bottom + gap;
            let left = btnRect.right - menuRect.width;

            const spaceBelow = window.innerHeight - btnRect.bottom;
            const spaceAbove = btnRect.top;

            // Если снизу мало места — открываем вверх
            if (spaceBelow < menuRect.height + gap && spaceAbove > spaceBelow) {
                top = btnRect.top - menuRect.height - gap;
            }

            // Ограничение по горизонтали
            if (left < 8) left = 8;
            if (left + menuRect.width > window.innerWidth - 8) {
                left = window.innerWidth - menuRect.width - 8;
            }

            // Ограничение по вертикали
            if (top < 8) top = 8;
            if (top + menuRect.height > window.innerHeight - 8) {
                top = Math.max(8, window.innerHeight - menuRect.height - 8);
            }

            menu.style.left = left + 'px';
            menu.style.top = top + 'px';
            menu.style.visibility = '';
        }

        function moveMenuToBody(dd, menu) {
            if (menu.__placeholder) return;

            const placeholder = document.createComment('actions-menu-placeholder');
            menu.__placeholder = placeholder;
            dd.insertBefore(placeholder, menu);
            document.body.appendChild(menu);
        }

        function repositionOpenMenu() {
            if (!openState) return;

            if (!isButtonVisibleInTableWrap(openState.btn)) {
                closeAll();
                return;
            }

            placeMenu(openState.btn, openState.menu);
        }

        // ID для связи dropdown <-> menu
        dropdowns.forEach((dd, index) => {
            dd.dataset.dropdownId = String(index + 1);
        });

        dropdowns.forEach((dd) => {
            const btn = dd.querySelector('[data-actions-toggle]');
            const menu = dd.querySelector('[data-actions-menu]');
            if (!btn || !menu) return;

            menu.setAttribute('data-actions-menu-owner', dd.dataset.dropdownId);

            btn.addEventListener('click', function (e) {
                e.stopPropagation();

                const isOpen = menu.classList.contains('is-open');
                closeAll();

                if (!isOpen) {
                    document.dispatchEvent(new CustomEvent('tms:dropdown-open', { detail: { id: 'actions-menu' } }));
                    moveMenuToBody(dd, menu);
                    menu.classList.add('is-open');
                    btn.setAttribute('aria-expanded', 'true');
                    setRowHighlight(dd, true);
                    placeMenu(btn, menu);
                    openState = { btn, menu, dd };
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

        document.addEventListener('tms:dropdown-open', function (e) {
            if (e.detail.id !== 'actions-menu') closeAll();
        });

        document.addEventListener('tms:drag-scroll-start', closeAll);

        window.addEventListener('resize', repositionOpenMenu);
        window.addEventListener('scroll', repositionOpenMenu, true);
        document.addEventListener('tms:columns-updated', repositionOpenMenu);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();