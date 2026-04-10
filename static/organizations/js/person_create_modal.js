document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("create-person-form");
    if (!form) return;

    var phoneInput = form.querySelector('[data-phone-mask]');
    if (phoneInput && window.PhoneMask) {
        PhoneMask.init(phoneInput);
    }

    var modal = document.getElementById("create-person-modal");
    var errorsBox = document.getElementById("cp-errors");
    var submitBtn = form.querySelector('button[type="submit"]');

    var fieldMap = {
        surname: "cp-surname",
        name: "cp-name",
        patronymic: "cp-patronymic",
        phone: "cp-phone",
        employer_id: null
    };

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        ModalHelpers.clearErrors(modal);
        ModalHelpers.setSubmitting(submitBtn, true);

        var data = new FormData(form);
        data.append("employer_id", form.dataset.employerId);

        fetch(form.dataset.url, {
            method: "POST",
            body: data,
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
            .then(function (resp) { return resp.json().then(function (body) { return { ok: resp.ok, body: body }; }); })
            .then(function (result) {
                if (result.ok) {
                    window.location.reload();
                    return;
                }
                ModalHelpers.applyFieldErrors(modal, fieldMap, result.body.errors || {}, errorsBox);
                ModalHelpers.setSubmitting(submitBtn, false);
            })
            .catch(function () {
                ModalHelpers.showGeneralError(errorsBox, "Ошибка сети. Попробуйте ещё раз.");
                ModalHelpers.setSubmitting(submitBtn, false);
            });
    });

    if (modal) {
        ModalHelpers.setupResetOnClose(modal);
    }
});
