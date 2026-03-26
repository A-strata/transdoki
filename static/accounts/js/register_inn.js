/**
 * ИНН-автозаполнение на странице регистрации.
 * URL API передаётся через data-api-url на элементе .inn-wrap.
 */
(function () {
    var innWrap = document.querySelector('.inn-wrap[data-api-url]');
    var innInput = document.getElementById('id_inn');
    var nameInput = document.getElementById('id_company_name');
    var hint = document.getElementById('autofill-hint');
    var spin = document.getElementById('inn-spin');

    if (!innInput || !nameInput || !innWrap) return;

    var apiUrl = innWrap.dataset.apiUrl;
    var timer = null;
    var autofilled = false;

    innInput.addEventListener('input', function () {
        var digits = this.value.replace(/\D/g, '');
        if (this.value !== digits) this.value = digits;

        clearTimeout(timer);
        spin.classList.remove('active');
        hint.classList.remove('visible');

        if (digits.length < 10) {
            if (autofilled) {
                nameInput.value = '';
                autofilled = false;
            }
            return;
        }

        hint.classList.add('visible');
        spin.classList.add('active');
        nameInput.placeholder = 'Загружаем…';

        timer = setTimeout(function () {
            fetch(apiUrl + '?inn=' + encodeURIComponent(digits))
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (data) {
                    spin.classList.remove('active');
                    hint.classList.remove('visible');
                    nameInput.placeholder = 'Заполнится по ИНН';
                    if (data && data.short_name) {
                        nameInput.value = data.short_name;
                        autofilled = true;
                    }
                })
                .catch(function () {
                    spin.classList.remove('active');
                    hint.classList.remove('visible');
                    nameInput.placeholder = 'Заполнится по ИНН';
                });
        }, 600);
    });

    nameInput.addEventListener('input', function () {
        autofilled = false;
    });
})();
