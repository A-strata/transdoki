document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("create-vehicle-form");
    if (!form) return;

    var grnInput = form.querySelector('[data-grn-mask]');
    if (grnInput && typeof initGrnMask === 'function') {
        initGrnMask(grnInput);
    }

    var modal = document.getElementById("create-vehicle-modal");
    var errorsBox = document.getElementById("cv-errors");
    var submitBtn = form.querySelector('button[type="submit"]');

    var fieldMap = {
        grn: "cv-grn",
        brand: "cv-brand",
        model: "cv-model",
        vehicle_type: "cv-vehicle-type",
        property_type: "cv-property-type",
        owner_id: null
    };

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        ModalHelpers.clearErrors(modal);
        ModalHelpers.setSubmitting(submitBtn, true);

        var data = new FormData(form);
        data.append("owner_id", form.dataset.ownerId);

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
