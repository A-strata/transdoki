// Клик по строке таблицы рейсов — переход в карточку.
// Обычный клик — текущая вкладка. Ctrl/Cmd+клик или средняя кнопка — новая вкладка.
// Игнорирует клики по интерактивным элементам и выделение текста.
(function () {
    function isInteractive(el) {
        return !!el.closest('a, button, input, textarea, select, label, summary, [data-docs-dropdown]');
    }

    function init() {
        // Запоминаем наличие выделения на mousedown,
        // потому что к моменту click браузер уже сбросит его.
        var hadSelection = false;

        document.addEventListener('mousedown', function (e) {
            if (e.button !== 0) return;
            var sel = window.getSelection();
            hadSelection = !!(sel && !sel.isCollapsed);
        });

        document.addEventListener('click', function (e) {
            if (e.button !== 0) return;

            var row = e.target.closest('tr[data-detail-url]');
            if (!row) return;
            if (isInteractive(e.target)) return;

            // Если на mousedown было выделение — этот клик его сбрасывает, не переходим
            if (hadSelection) return;

            // Если пользователь выделил текст протяжкой (mousedown→mousemove→mouseup)
            var selection = window.getSelection();
            if (selection && !selection.isCollapsed) return;

            var url = row.getAttribute('data-detail-url');
            if (!url) return;

            if (e.ctrlKey || e.metaKey) {
                window.open(url, '_blank');
            } else {
                location.href = url;
            }
        });

        // Средняя кнопка мыши — открыть в новой вкладке
        document.addEventListener('auxclick', function (e) {
            if (e.button !== 1) return;

            var row = e.target.closest('tr[data-detail-url]');
            if (!row) return;
            if (isInteractive(e.target)) return;

            var url = row.getAttribute('data-detail-url');
            if (!url) return;

            e.preventDefault();
            window.open(url, '_blank');
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
