(function () {
    const form      = document.getElementById('deposit-form');
    if (!form) return;

    const amountEl  = document.getElementById('id_amount');
    const amountErr = document.getElementById('amount-error');
    const globalErr = document.getElementById('global-error');
    const payBtn    = document.getElementById('pay-btn');

    const depositUrl     = form.dataset.depositUrl;
    const successUrl     = form.dataset.successUrl;

    // Быстрый выбор суммы
    document.querySelectorAll('.quick-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            amountEl.value = btn.dataset.amount;
            amountEl.focus();
        });
    });

    function setLoading(on) {
        payBtn.disabled = on;
        payBtn.classList.toggle('loading', on);
    }

    function showAmountError(msg) {
        amountEl.classList.add('is-invalid');
        amountErr.textContent = msg;
        amountErr.style.display = 'block';
    }

    function clearErrors() {
        amountEl.classList.remove('is-invalid');
        amountErr.style.display = 'none';
        globalErr.style.display = 'none';
    }

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        clearErrors();
        setLoading(true);

        // Шаг 1: POST на наш сервер → создаём PaymentOrder → получаем параметры для виджета
        fetch(depositUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value,
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({ amount: amountEl.value }),
        })
        .then(function (resp) { return resp.json(); })
        .then(function (data) {
            if (!data.ok) {
                // Ошибки валидации от сервера
                if (data.errors && data.errors.amount) {
                    showAmountError(data.errors.amount[0].message);
                } else if (data.errors && data.errors.__all__) {
                    globalErr.textContent = data.errors.__all__[0].message;
                    globalErr.style.display = 'block';
                }
                setLoading(false);
                return;
            }

            // Шаг 2: открываем виджет CloudPayments с полученными параметрами
            var widget = new cp.CloudPayments({ language: 'ru-RU' });
            widget.pay('charge', data.widget_params, {
                onSuccess: function () {
                    // Деньги списаны. Webhook обработается асинхронно,
                    // поэтому баланс может отобразиться через несколько секунд.
                    window.location.href = successUrl;
                },
                onFail: function (reason) {
                    globalErr.textContent = 'Оплата не прошла: ' + (reason || 'попробуйте ещё раз');
                    globalErr.style.display = 'block';
                    setLoading(false);
                },
                onComplete: function () {
                    // onComplete вызывается всегда — после success и fail.
                    // Кнопку разблокируем только в onFail, чтобы не было двойного нажатия.
                }
            });
        })
        .catch(function () {
            globalErr.textContent = 'Ошибка соединения. Проверьте сеть и попробуйте снова.';
            globalErr.style.display = 'block';
            setLoading(false);
        });
    });
}());
