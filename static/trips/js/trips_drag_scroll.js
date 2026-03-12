// Drag-scroll таблицы ЛКМ (горизонтально таблица + вертикально окно)
(function () {
    function init() {
        const wrap = document.querySelector('[data-drag-scroll]');
        if (!wrap) return;

        let isDown = false;
        let startX = 0;
        let startY = 0;
        let startScrollLeft = 0;
        let startWindowY = 0;
        let moved = false;

        function isInteractive(el) {
            return !!el.closest('a, button, input, textarea, select, label, summary');
        }

        wrap.addEventListener('mousedown', function (e) {
            if (e.button !== 0) return;
            if (isInteractive(e.target)) return;

            isDown = true;
            moved = false;
            wrap.classList.add('is-dragging');

            startX = e.clientX;
            startY = e.clientY;
            startScrollLeft = wrap.scrollLeft;
            startWindowY = window.scrollY;
        });

        document.addEventListener('mousemove', function (e) {
            if (!isDown) return;

            const dx = e.clientX - startX;
            const dy = e.clientY - startY;

            if (Math.abs(dx) > 2 || Math.abs(dy) > 2) moved = true;

            wrap.scrollLeft = startScrollLeft - dx;
            window.scrollTo({ top: startWindowY - dy, behavior: 'auto' });

            e.preventDefault();
        });

        document.addEventListener('mouseup', function () {
            if (!isDown) return;
            isDown = false;
            wrap.classList.remove('is-dragging');
        });

        wrap.addEventListener('dragstart', function (e) {
            e.preventDefault();
        });

        wrap.addEventListener('click', function (e) {
            if (moved) {
                e.preventDefault();
                e.stopPropagation();
                moved = false;
            }
        }, true);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();