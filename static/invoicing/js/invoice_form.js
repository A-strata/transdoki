(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        // Поле заказчика рендерится Django как <select id="id_customer">
        // с data-search-url. initAutocomplete оборачивает его в поисковый
        // input и подгружает организации по мере ввода.
        if (document.getElementById('id_customer')) {
            initAutocomplete('id_customer');
        }
    });
})();
