// Dropdown "Документы" в строках таблицы рейсов:
// - меню переносится в body (не обрезается overflow таблицы)
// - умное позиционирование: вниз по умолчанию, вверх если мало места
// - подсветка строки при открытом меню
// - закрывается по клику вне, Escape, скроллу таблицы
(function () {
    function init() {
        var openState = null;

        function closeAll() {
            if (!openState) return;

            var s = openState;
            openState = null;

            s.menu.classList.remove('is-open');
            s.btn.setAttribute('aria-expanded', 'false');

            if (s.row) {
                s.row.classList.remove('is-docs-open');
            }

            // Вернуть меню в DOM после завершения анимации
            setTimeout(function () {
                if (s.placeholder && s.placeholder.parentNode) {
                    s.placeholder.parentNode.insertBefore(s.menu, s.placeholder);
                    s.placeholder.remove();
                }
                s.menu.style.top = '';
                s.menu.style.left = '';
            }, 150);
        }

        function placeMenu(btn, menu) {
            var btnRect = btn.getBoundingClientRect();
            var gap = 6;

            // Показать для замера, но невидимо
            menu.style.visibility = 'hidden';
            menu.style.opacity = '0';
            menu.classList.add('is-open');

            var menuRect = menu.getBoundingClientRect();

            var spaceBelow = window.innerHeight - btnRect.bottom;
            var spaceAbove = btnRect.top;

            // Вниз по умолчанию, вверх если снизу не влезает
            var top;
            if (spaceBelow >= menuRect.height + gap || spaceBelow >= spaceAbove) {
                top = btnRect.bottom + gap;
            } else {
                top = btnRect.top - menuRect.height - gap;
            }

            // Правый край меню по правому краю кнопки
            var left = btnRect.right - menuRect.width;

            // Ограничения viewport
            if (left < 8) left = 8;
            if (left + menuRect.width > window.innerWidth - 8) {
                left = window.innerWidth - menuRect.width - 8;
            }
            if (top < 8) top = 8;
            if (top + menuRect.height > window.innerHeight - 8) {
                top = Math.max(8, window.innerHeight - menuRect.height - 8);
            }

            menu.style.top = top + 'px';
            menu.style.left = left + 'px';
            menu.style.visibility = '';
            menu.style.opacity = '';
        }

        document.addEventListener('click', function (e) {
            var toggle = e.target.closest('[data-docs-toggle]');

            if (toggle) {
                e.preventDefault();
                e.stopPropagation();

                var dropdown = toggle.closest('[data-docs-dropdown]');
                var menu = dropdown ? dropdown.querySelector('[data-docs-menu]') : null;
                if (!menu) return;

                var wasOpen = openState && openState.menu === menu;
                closeAll();

                if (!wasOpen) {
                    document.dispatchEvent(new CustomEvent('tms:dropdown-open', { detail: { id: 'docs-menu' } }));

                    var placeholder = document.createComment('docs-menu-placeholder');
                    dropdown.insertBefore(placeholder, menu);
                    document.body.appendChild(menu);

                    var row = toggle.closest('tr[data-trip-row]');
                    if (row) row.classList.add('is-docs-open');

                    placeMenu(toggle, menu);
                    toggle.setAttribute('aria-expanded', 'true');
                    openState = { menu: menu, btn: toggle, placeholder: placeholder, row: row };
                }

                return;
            }

            if (openState && !openState.menu.contains(e.target)) {
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

        window.addEventListener('scroll', function () {
            if (openState) placeMenu(openState.btn, openState.menu);
        }, true);

        window.addEventListener('resize', function () {
            if (openState) closeAll();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
