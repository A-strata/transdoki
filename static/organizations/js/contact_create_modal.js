document.addEventListener("DOMContentLoaded", function () {
    // ── Создание контактного лица ──

    var form = document.getElementById("create-contact-form");
    if (!form) return;

    var modal = document.getElementById("create-contact-modal");
    var errorsBox = document.getElementById("cp-errors");
    var submitBtn = form.querySelector('button[type="submit"]');

    var fieldMap = {
        name: "cp-name",
        phone: "cp-phone",
        position: "cp-position"
    };

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        ModalHelpers.clearErrors(modal);
        ModalHelpers.setSubmitting(submitBtn, true);

        var data = new FormData(form);
        data.append("org_id", form.dataset.orgId);

        fetch(form.dataset.url, {
            method: "POST",
            body: data,
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
            .then(function (resp) {
                return resp.json().then(function (body) { return { ok: resp.ok, body: body }; });
            })
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

    // ── Редактирование контактного лица ──

    var editForm = document.getElementById("edit-contact-form");
    if (editForm) {
        var editModal = document.getElementById("edit-contact-modal");
        var editErrorsBox = document.getElementById("ecp-errors");
        var editSubmitBtn = editForm.querySelector('button[type="submit"]');

        var editFieldMap = {
            name: "ecp-name",
            phone: "ecp-phone",
            position: "ecp-position"
        };

        document.addEventListener("click", function (e) {
            var btn = e.target.closest('[data-modal-open="edit-contact-modal"]');
            if (!btn) return;
            document.getElementById("ecp-id").value = btn.dataset.contactId;
            document.getElementById("ecp-name").value = btn.dataset.contactName;
            var phoneInput = document.getElementById("ecp-phone");
            var rawPhone = btn.dataset.contactPhone || "";
            if (phoneInput._phoneMask) {
                var digits = rawPhone.replace(/\D/g, "");
                if (digits.length === 11 && digits.charAt(0) === "7") digits = digits.slice(1);
                phoneInput._phoneMask.unmaskedValue = digits;
            } else {
                phoneInput.value = rawPhone;
            }
            document.getElementById("ecp-position").value = btn.dataset.contactPosition || "";
        });

        editForm.addEventListener("submit", function (e) {
            e.preventDefault();
            ModalHelpers.clearErrors(editModal);
            ModalHelpers.setSubmitting(editSubmitBtn, true);

            var data = new FormData(editForm);

            fetch(editForm.dataset.url, {
                method: "POST",
                body: data,
                headers: { "X-Requested-With": "XMLHttpRequest" }
            })
                .then(function (resp) {
                    return resp.json().then(function (body) { return { ok: resp.ok, body: body }; });
                })
                .then(function (result) {
                    if (result.ok || result.body.ok) {
                        window.location.reload();
                        return;
                    }
                    ModalHelpers.applyFieldErrors(editModal, editFieldMap, result.body.errors || {}, editErrorsBox);
                    ModalHelpers.setSubmitting(editSubmitBtn, false);
                })
                .catch(function () {
                    ModalHelpers.showGeneralError(editErrorsBox, "Ошибка сети. Попробуйте ещё раз.");
                    ModalHelpers.setSubmitting(editSubmitBtn, false);
                });
        });

        if (editModal) {
            ModalHelpers.setupResetOnClose(editModal);
        }
    }

    // ── Удаление контактного лица ──

    var deleteModal = document.getElementById("delete-contact-modal");
    var deleteForm = document.getElementById("delete-contact-form");
    if (!deleteModal || !deleteForm) return;

    var deleteNameSpan = document.getElementById("delete-contact-name");
    var deleteIdInput = document.getElementById("delete-contact-id");

    document.addEventListener("click", function (e) {
        var btn = e.target.closest('[data-modal-open="delete-contact-modal"]');
        if (!btn) return;
        deleteNameSpan.textContent = btn.dataset.contactName;
        deleteIdInput.value = btn.dataset.contactId;
    });

    deleteForm.addEventListener("submit", function (e) {
        e.preventDefault();

        var deleteBtn = deleteForm.querySelector('button[type="submit"]');
        ModalHelpers.setSubmitting(deleteBtn, true);

        var data = new FormData(deleteForm);

        fetch(deleteForm.dataset.url, {
            method: "POST",
            body: data,
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
            .then(function (resp) {
                return resp.json().then(function (body) { return { ok: resp.ok, body: body }; });
            })
            .then(function (result) {
                if (result.ok || result.body.ok) {
                    window.location.reload();
                    return;
                }
                alert(result.body.error || "Ошибка при удалении");
                ModalHelpers.setSubmitting(deleteBtn, false);
            })
            .catch(function () {
                alert("Ошибка сети. Попробуйте ещё раз.");
                ModalHelpers.setSubmitting(deleteBtn, false);
            });
    });
});
