document.addEventListener("DOMContentLoaded", function () {
    /* ── Утилиты ── */
    function getCsrf() {
        for (var c of document.cookie.split(";")) {
            var p = c.trim().split("=");
            if (p[0] === "csrftoken") return decodeURIComponent(p[1]);
        }
        return "";
    }

    /* ── Модалка добавления пользователя ── */
    var overlay     = document.getElementById("add-user-overlay");
    var submitBtn   = document.getElementById("add-user-submit");
    var errorBox    = document.getElementById("add-user-error");
    var formBody    = document.getElementById("au-form-body");
    var credentials = document.getElementById("au-credentials");
    var credClose   = document.getElementById("au-cred-close");

    /*
     * Сброс модалки при открытии через data-modal-open (base.js).
     * Очистка полей, ошибок, переключение на экран формы.
     * Ошибки (.modal-field-error) управляются через style.display,
     * а не через ModalHelpers — элементы статические (data-err паттерн).
     */
    function resetModal() {
        overlay.querySelectorAll(".modal-field input, .modal-field select").forEach(function (el) {
            el.value = "";
            el.classList.remove("is-invalid");
        });
        overlay.querySelectorAll(".modal-field-error").forEach(function (el) {
            el.style.display = "none";
            el.textContent = "";
        });
        errorBox.hidden = true;
        errorBox.textContent = "";
        formBody.hidden = false;
        credentials.hidden = true;
        ModalHelpers.setSubmitting(submitBtn, false);
    }

    /*
     * Сброс при закрытии модалки (base.js ставит hidden = true
     * через Escape, клик по overlay или data-modal-close).
     * Сброс именно при закрытии, а не при открытии — иначе
     * программное открытие из «Сбросить пароль» (credentials-экран)
     * будет перезатёрто resetModal().
     */
    if (overlay) {
        new MutationObserver(function (mutations) {
            for (var i = 0; i < mutations.length; i++) {
                if (mutations[i].attributeName === "hidden" && overlay.hidden) {
                    resetModal();
                }
            }
        }).observe(overlay, { attributes: true, attributeFilter: ["hidden"] });
    }

    function showCredentials(username, password) {
        document.getElementById("cred-login").textContent = username;
        document.getElementById("cred-pass").textContent = password;
        formBody.hidden = true;
        credentials.hidden = false;
    }

    credClose.addEventListener("click", function () {
        overlay.hidden = true;
        location.reload();
    });

    /* Копирование credentials */
    overlay.addEventListener("click", function (e) {
        if (e.target.classList.contains("copy-btn")) {
            var targetId = e.target.dataset.target;
            var text = document.getElementById(targetId).textContent;
            navigator.clipboard.writeText(text).then(function () {
                var orig = e.target.textContent;
                e.target.textContent = "Скопировано!";
                setTimeout(function () { e.target.textContent = orig; }, 1500);
            });
        }
    });

    /* Сброс пароля — открывает модалку программно, сразу в credentials-экране */
    document.querySelectorAll(".reset-pwd-btn").forEach(function (btn) {
        btn.addEventListener("click", async function () {
            if (!confirm("Сбросить пароль пользователя? Будет создан новый временный пароль.")) return;
            btn.disabled = true;
            btn.textContent = "Сбрасываем…";
            try {
                var resp = await fetch(btn.dataset.resetUrl, {
                    method: "POST",
                    headers: { "X-CSRFToken": getCsrf(), "X-Requested-With": "XMLHttpRequest" },
                });
                var data = await resp.json();
                if (data.ok) {
                    formBody.hidden = true;
                    showCredentials(data.username, data.temp_password);
                    overlay.hidden = false;
                } else {
                    alert(data.error || "Ошибка сброса пароля.");
                }
            } catch (_) {
                alert("Ошибка соединения.");
            } finally {
                btn.disabled = false;
                btn.textContent = "Сбросить пароль";
            }
        });
    });

    /* Создание пользователя */
    submitBtn.addEventListener("click", async function () {
        /* Очистка ошибок */
        overlay.querySelectorAll(".modal-field-error").forEach(function (el) {
            el.style.display = "none";
            el.textContent = "";
        });
        overlay.querySelectorAll(".modal-field input, .modal-field select").forEach(function (el) {
            el.classList.remove("is-invalid");
        });
        errorBox.hidden = true;

        var params = new URLSearchParams();
        ["first_name", "last_name", "role"].forEach(function (name) {
            var el = overlay.querySelector("[name='" + name + "']");
            if (el) params.set(name, el.value.trim());
        });

        ModalHelpers.setSubmitting(submitBtn, true);

        var createUrl = submitBtn.dataset.createUrl;
        try {
            var resp = await fetch(createUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCsrf(),
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: params.toString(),
            });
            var data = await resp.json();
            if (data.ok) {
                showCredentials(data.username, data.temp_password);
            } else {
                var errors = data.errors || {};
                var hasField = false;
                for (var field in errors) {
                    var errEl = overlay.querySelector("[data-err='" + field + "']");
                    var inputEl = overlay.querySelector("[name='" + field + "']");
                    if (errEl) {
                        errEl.textContent = errors[field];
                        errEl.style.display = "block";
                        hasField = true;
                    }
                    if (inputEl) inputEl.classList.add("is-invalid");
                }
                if (!hasField) {
                    errorBox.textContent = Object.values(errors).join("; ") || "Ошибка";
                    errorBox.hidden = false;
                }
                ModalHelpers.setSubmitting(submitBtn, false);
            }
        } catch (_) {
            errorBox.textContent = "Ошибка соединения.";
            errorBox.hidden = false;
            ModalHelpers.setSubmitting(submitBtn, false);
        }
    });

    /* ── Редактор ролей и имён ── */
    document.querySelectorAll(".role-form").forEach(function (form) {
        const select    = form.querySelector(".role-select");
        const toggleBtn = form.querySelector(".role-toggle-btn");
        const saveBtn   = form.querySelector(".role-save-btn");
        const updateUrl = form.dataset.updateUrl;

        if (!select || !toggleBtn || !saveBtn) return;

        const namesOnly = form.dataset.namesOnly === "1";
        const row = form.closest("tr");
        const lastNameDisplay  = row ? row.querySelector(".col-last-name .name-display")  : null;
        const lastNameInput    = row ? row.querySelector(".col-last-name .name-edit")     : null;
        const firstNameDisplay = row ? row.querySelector(".col-first-name .name-display") : null;
        const firstNameInput   = row ? row.querySelector(".col-first-name .name-edit")   : null;

        let initialRole  = select.dataset.initial || select.value;
        let initialLast  = lastNameInput  ? lastNameInput.value  : "";
        let initialFirst = firstNameInput ? firstNameInput.value : "";
        let isEditing = false;

        function hasChanges() {
            return (!namesOnly && select.value !== initialRole)
                || (lastNameInput  && lastNameInput.value  !== initialLast)
                || (firstNameInput && firstNameInput.value !== initialFirst);
        }

        function updateSaveVisibility() {
            saveBtn.classList.toggle("is-visible", isEditing && hasChanges());
            saveBtn.disabled = !(isEditing && hasChanges());
        }

        function setEditMode(next) {
            isEditing = next;
            if (!namesOnly) select.disabled = !isEditing;
            toggleBtn.textContent = isEditing ? "Отмена" : "Редактировать";

            if (lastNameDisplay)  lastNameDisplay.hidden  = isEditing;
            if (lastNameInput)    lastNameInput.hidden    = !isEditing;
            if (firstNameDisplay) firstNameDisplay.hidden = isEditing;
            if (firstNameInput)   firstNameInput.hidden   = !isEditing;

            if (!isEditing) {
                select.value = initialRole;
                if (lastNameInput)  lastNameInput.value  = initialLast;
                if (firstNameInput) firstNameInput.value = initialFirst;
            }
            updateSaveVisibility();
        }

        toggleBtn.addEventListener("click", function () { setEditMode(!isEditing); });
        select.addEventListener("change", updateSaveVisibility);
        if (lastNameInput)  lastNameInput.addEventListener("input", updateSaveVisibility);
        if (firstNameInput) firstNameInput.addEventListener("input", updateSaveVisibility);

        form.addEventListener("submit", async function (e) {
            e.preventDefault();

            saveBtn.disabled = true;
            saveBtn.textContent = "Сохраняем…";
            toggleBtn.disabled = true;

            var params = new URLSearchParams();
            params.set("role", select.value);
            if (lastNameInput)  params.set("last_name",  lastNameInput.value.trim());
            if (firstNameInput) params.set("first_name", firstNameInput.value.trim());

            try {
                var resp = await fetch(updateUrl, {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": getCsrf(),
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    body: params.toString(),
                });
                var data = await resp.json();
                if (data.ok) {
                    initialLast  = data.last_name  || "";
                    initialFirst = data.first_name || "";
                    initialRole  = select.value;

                    if (lastNameDisplay)  lastNameDisplay.textContent  = data.last_name  || "—";
                    if (firstNameDisplay) firstNameDisplay.textContent = data.first_name || "—";

                    setEditMode(false);
                } else {
                    alert(data.error || "Ошибка сохранения.");
                }
            } catch (_) {
                alert("Ошибка соединения.");
            } finally {
                saveBtn.disabled = false;
                saveBtn.textContent = "Сохранить";
                toggleBtn.disabled = false;
            }
        });

        setEditMode(false);
    });
});
