(function () {
    function init() {
        const wrap = document.querySelector('[data-drag-scroll]');
        if (!wrap) return;

        let isDown = false;
        let startX = 0;
        let startY = 0;
        let startScrollLeft = 0;
        let startScrollTop = 0;
        let moved = false;
        let dragRow = null;

        function isInteractive(el) {
            return !!el.closest('a, button, input, textarea, select, label, summary');
        }

        function clearDragRow() {
            if (dragRow) {
                dragRow.classList.remove('is-drag-source');
                dragRow = null;
            }
        }

        wrap.addEventListener('mousedown', function (e) {
            if (e.button !== 0) return;
            if (isInteractive(e.target)) return;

            isDown = true;
            moved = false;
            wrap.classList.add('is-dragging');
            document.dispatchEvent(new CustomEvent('tms:drag-scroll-start'));

            startX = e.clientX;
            startY = e.clientY;
            startScrollLeft = wrap.scrollLeft;
            startScrollTop = wrap.scrollTop;

            clearDragRow();
            dragRow = e.target.closest('tr[data-trip-row]');
            if (dragRow) {
                dragRow.classList.add('is-drag-source');
            }
        });

        document.addEventListener('mousemove', function (e) {
            if (!isDown) return;

            const dx = e.clientX - startX;
            const dy = e.clientY - startY;

            if (Math.abs(dx) > 2 || Math.abs(dy) > 2) moved = true;

            wrap.scrollLeft = startScrollLeft - dx;
            wrap.scrollTop = startScrollTop - dy;

            e.preventDefault();
        });

        document.addEventListener('mouseup', function () {
            if (!isDown) return;

            isDown = false;
            wrap.classList.remove('is-dragging');
            clearDragRow();
        });

        wrap.addEventListener('mouseleave', function () {
            if (!isDown) return;
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