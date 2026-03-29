document.addEventListener('DOMContentLoaded', function() {
    var fillButton = document.getElementById('btn_fill_inn');
    if (!fillButton) return;

    var innInput = document.getElementById('id_inn');

    function clearFieldErrors(input) {
        if (!input) return;
        input.classList.remove('is-invalid');
        var group = input.closest('.form-group') || input.closest('.input-wrap');
        if (!group) return;
        var errorList = group.querySelector('.errorlist');
        if (errorList) errorList.remove();
    }

    function setFieldError(input, message) {
        if (!input) return;
        input.classList.add('is-invalid');
        var group = input.closest('.form-group') || input.closest('.input-wrap');
        if (!group) return;
        var errorList = group.querySelector('.errorlist');
        if (!errorList) {
            errorList = document.createElement('ul');
            errorList.className = 'errorlist';
            group.appendChild(errorList);
        }
        errorList.innerHTML = '<li>' + message + '</li>';
    }

    fillButton.addEventListener('click', function() {
        var inn = innInput.value.trim();

        if (inn.length !== 10 && inn.length !== 12) {
            setFieldError(innInput, 'Введите корректный ИНН (10 или 12 цифр)');
            return;
        }

        clearFieldErrors(innInput);
        fillButton.disabled = true;
        fillButton.textContent = 'Загрузка\u2026';

        fetch('/organizations/api/suggestions_by_inn/?inn=' + encodeURIComponent(inn))
            .then(function(response) { return response.json(); })
            .then(function(data) {
                if (data.error) {
                    setFieldError(innInput, data.error);
                    return;
                }

                var fields = {
                    'id_full_name': data.full_name,
                    'id_short_name': data.short_name,
                    'id_address': data.address,
                    'id_ogrn': data.ogrn,
                    'id_kpp': data.kpp
                };

                for (var id in fields) {
                    var el = document.getElementById(id);
                    if (el) {
                        el.value = fields[id] || '';
                        clearFieldErrors(el);
                    }
                }

                clearFieldErrors(innInput);
            })
            .catch(function() {
                setFieldError(innInput, 'Ошибка при получении данных');
            })
            .finally(function() {
                fillButton.disabled = false;
                fillButton.textContent = 'Заполнить по ИНН';
            });
    });
});
