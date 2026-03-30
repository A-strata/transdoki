document.addEventListener("DOMContentLoaded", function () {
    // ── Создание контактного лица ──

    var form = document.getElementById("create-contact-form");
    if (!form) return;

    var errorsBox = document.getElementById("cp-errors");
    var submitBtn = form.querySelector('button[type="submit"]');
    var originalText = submitBtn.textContent;

    var fieldMap = {
        name: "cp-name",
        phone: "cp-phone",
        position: "cp-position"
    };

    function clearErrors() {
        errorsBox.hidden = true;
        errorsBox.innerHTML = "";
        form.querySelectorAll(".modal-field-error").forEach(function (el) { el.remove(); });
        form.querySelectorAll(".is-invalid").forEach(function (el) { el.classList.remove("is-invalid"); });
    }

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        clearErrors();

        submitBtn.disabled = true;
        submitBtn.textContent = "Сохранение...";

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

                var errors = result.body.errors || {};
                var generalErrors = [];

                for (var field in errors) {
                    var inputId = fieldMap[field];
                    if (inputId) {
                        var input = document.getElementById(inputId);
                        if (input) {
                            input.classList.add("is-invalid");
                            var errEl = document.createElement("p");
                            errEl.className = "modal-field-error";
                            errEl.textContent = errors[field];
                            input.parentNode.appendChild(errEl);
                            continue;
                        }
                    }
                    generalErrors.push(errors[field]);
                }

                if (generalErrors.length) {
                    errorsBox.textContent = generalErrors.join(". ");
                    errorsBox.hidden = false;
                }

                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            })
            .catch(function () {
                errorsBox.textContent = "Ошибка сети. Попробуйте ещё раз.";
                errorsBox.hidden = false;
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            });
    });

    // Reset on modal close
    var modal = document.getElementById("create-contact-modal");
    if (modal) {
        var observer = new MutationObserver(function (mutations) {
            mutations.forEach(function (m) {
                if (m.attributeName === "hidden" && modal.hidden) {
                    form.reset();
                    clearErrors();
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalText;
                }
            });
        });
        observer.observe(modal, { attributes: true });
    }

    // ── Редактирование контактного лица ──

    var editForm = document.getElementById("edit-contact-form");
    if (editForm) {
        var editErrorsBox = document.getElementById("ecp-errors");
        var editSubmitBtn = editForm.querySelector('button[type="submit"]');
        var editOriginalText = editSubmitBtn.textContent;

        var editFieldMap = {
            name: "ecp-name",
            phone: "ecp-phone",
            position: "ecp-position"
        };

        function clearEditErrors() {
            editErrorsBox.hidden = true;
            editErrorsBox.innerHTML = "";
            editForm.querySelectorAll(".modal-field-error").forEach(function (el) { el.remove(); });
            editForm.querySelectorAll(".is-invalid").forEach(function (el) { el.classList.remove("is-invalid"); });
        }

        // Populate from data-attributes
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
            clearEditErrors();

            editSubmitBtn.disabled = true;
            editSubmitBtn.textContent = "Сохранение...";

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

                    var errors = result.body.errors || {};
                    var generalErrors = [];

                    for (var field in errors) {
                        var inputId = editFieldMap[field];
                        if (inputId) {
                            var input = document.getElementById(inputId);
                            if (input) {
                                input.classList.add("is-invalid");
                                var errEl = document.createElement("p");
                                errEl.className = "modal-field-error";
                                errEl.textContent = errors[field];
                                input.parentNode.appendChild(errEl);
                                continue;
                            }
                        }
                        generalErrors.push(errors[field]);
                    }

                    if (generalErrors.length) {
                        editErrorsBox.textContent = generalErrors.join(". ");
                        editErrorsBox.hidden = false;
                    }

                    editSubmitBtn.disabled = false;
                    editSubmitBtn.textContent = editOriginalText;
                })
                .catch(function () {
                    editErrorsBox.textContent = "Ошибка сети. Попробуйте ещё раз.";
                    editErrorsBox.hidden = false;
                    editSubmitBtn.disabled = false;
                    editSubmitBtn.textContent = editOriginalText;
                });
        });

        // Reset on modal close
        var editModal = document.getElementById("edit-contact-modal");
        if (editModal) {
            var editObserver = new MutationObserver(function (mutations) {
                mutations.forEach(function (m) {
                    if (m.attributeName === "hidden" && editModal.hidden) {
                        editForm.reset();
                        clearEditErrors();
                        editSubmitBtn.disabled = false;
                        editSubmitBtn.textContent = editOriginalText;
                    }
                });
            });
            editObserver.observe(editModal, { attributes: true });
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
        deleteBtn.disabled = true;
        deleteBtn.textContent = "Удаление...";

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
                deleteBtn.disabled = false;
                deleteBtn.textContent = "Удалить";
            })
            .catch(function () {
                alert("Ошибка сети. Попробуйте ещё раз.");
                deleteBtn.disabled = false;
                deleteBtn.textContent = "Удалить";
            });
    });
});
