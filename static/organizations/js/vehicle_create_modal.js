document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("create-vehicle-form");
    if (!form) return;

    var errorsBox = document.getElementById("cv-errors");
    var submitBtn = form.querySelector('button[type="submit"]');
    var originalText = submitBtn.textContent;

    form.addEventListener("submit", function (e) {
        e.preventDefault();

        errorsBox.hidden = true;
        errorsBox.innerHTML = "";

        // Clear field-level errors
        form.querySelectorAll(".modal-field-error").forEach(function (el) {
            el.remove();
        });
        form.querySelectorAll(".is-invalid").forEach(function (el) {
            el.classList.remove("is-invalid");
        });

        submitBtn.disabled = true;
        submitBtn.textContent = submitBtn.dataset.loadingText || "Сохранение...";

        var data = new FormData(form);
        data.append("owner_id", form.dataset.ownerId);

        fetch(form.dataset.url, {
            method: "POST",
            body: data,
            headers: {
                "X-Requested-With": "XMLHttpRequest"
            }
        })
            .then(function (resp) { return resp.json().then(function (body) { return { ok: resp.ok, body: body }; }); })
            .then(function (result) {
                if (result.ok) {
                    window.location.reload();
                    return;
                }

                var errors = result.body.errors || {};
                var fieldMap = {
                    grn: "cv-grn",
                    brand: "cv-brand",
                    model: "cv-model",
                    vehicle_type: "cv-vehicle-type",
                    property_type: "cv-property-type",
                    owner_id: null
                };

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

    // Reset form on modal close
    var modal = document.getElementById("create-vehicle-modal");
    if (modal) {
        var observer = new MutationObserver(function (mutations) {
            mutations.forEach(function (m) {
                if (m.attributeName === "hidden" && modal.hidden) {
                    form.reset();
                    errorsBox.hidden = true;
                    errorsBox.innerHTML = "";
                    form.querySelectorAll(".modal-field-error").forEach(function (el) {
                        el.remove();
                    });
                    form.querySelectorAll(".is-invalid").forEach(function (el) {
                        el.classList.remove("is-invalid");
                    });
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalText;
                }
            });
        });
        observer.observe(modal, { attributes: true });
    }
});
