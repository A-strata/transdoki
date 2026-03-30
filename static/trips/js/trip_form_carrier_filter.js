document.addEventListener('DOMContentLoaded', function () {
    var carrierSelect = document.getElementById('id_carrier');
    if (!carrierSelect) return;

    var FILTERED_FIELDS = ['id_truck', 'id_trailer', 'id_driver'];

    // Сохраняем базовые URL при инициализации
    var baseUrls = {};
    FILTERED_FIELDS.forEach(function (id) {
        var select = document.getElementById(id);
        if (select) baseUrls[id] = select.dataset.searchUrl || '';
    });

    function applyCarrierFilter(carrierId) {
        FILTERED_FIELDS.forEach(function (id) {
            var select = document.getElementById(id);
            if (!select || !baseUrls[id]) return;

            if (carrierId) {
                var url = new URL(baseUrls[id], location.origin);
                url.searchParams.set('carrier_id', carrierId);
                select.dataset.searchUrl = url.toString();
                select.dataset.openOnFocus = '1';
            } else {
                select.dataset.searchUrl = baseUrls[id];
                delete select.dataset.openOnFocus;
            }
        });
    }

    carrierSelect.addEventListener('change', function () {
        applyCarrierFilter(carrierSelect.value || '');
    });

    // Применить сразу, если перевозчик уже выбран (редактирование или автоподстановка)
    if (carrierSelect.value) {
        applyCarrierFilter(carrierSelect.value);
    }
});
