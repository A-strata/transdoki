/**
 * ModalHelpers — общие функции для модальных окон.
 *
 * Namespace на window, подключается через <script> в base.html
 * ПЕРЕД скриптами отдельных модалок.
 */
(function () {
    "use strict";

    var ModalHelpers = {};

    /**
     * Очистить все ошибки валидации внутри модалки.
     * Снимает .is-invalid, удаляет .modal-field-error, скрывает .modal-form-errors.
     *
     * @param {HTMLElement} modal — .modal-overlay или любой контейнер
     */
    ModalHelpers.clearErrors = function (modal) {
        modal.querySelectorAll(".is-invalid").forEach(function (el) {
            el.classList.remove("is-invalid");
        });
        modal.querySelectorAll(".modal-field-error").forEach(function (el) {
            el.remove();
        });
        var box = modal.querySelector(".modal-form-errors");
        if (box) {
            box.textContent = "";
            box.hidden = true;
        }
    };

    /**
     * Показать ошибку под конкретным полем.
     *
     * @param {HTMLElement} modal — контейнер (для контекста, не используется напрямую)
     * @param {string}      inputId — id элемента input/select
     * @param {string}      message — текст ошибки
     * @returns {boolean} true если поле найдено и ошибка показана
     */
    ModalHelpers.showFieldError = function (modal, inputId, message) {
        var input = document.getElementById(inputId);
        if (!input || input.type === "hidden") return false;

        input.classList.add("is-invalid");
        var errEl = document.createElement("p");
        errEl.className = "modal-field-error";
        errEl.textContent = message;
        input.parentNode.appendChild(errEl);
        return true;
    };

    /**
     * Показать общую ошибку формы в .modal-form-errors.
     *
     * @param {HTMLElement} errorsBox — элемент .modal-form-errors
     * @param {string}      message  — текст ошибки
     */
    ModalHelpers.showGeneralError = function (errorsBox, message) {
        if (!errorsBox) return;
        errorsBox.textContent = message;
        errorsBox.hidden = false;
    };

    /**
     * Применить серверные ошибки к полям модалки через fieldMap.
     * Ошибки без соответствия в fieldMap попадают в общий блок.
     *
     * @param {HTMLElement} modal     — контейнер модалки
     * @param {Object}      fieldMap  — { serverField: "dom-input-id" | null }
     * @param {Object}      errors    — { field: "message", ... } от сервера
     * @param {HTMLElement} errorsBox — элемент .modal-form-errors
     */
    ModalHelpers.applyFieldErrors = function (modal, fieldMap, errors, errorsBox) {
        var generalErrors = [];

        for (var field in errors) {
            if (!errors.hasOwnProperty(field)) continue;

            var inputId = fieldMap[field];
            if (inputId) {
                var shown = ModalHelpers.showFieldError(modal, inputId, errors[field]);
                if (shown) continue;
            }
            generalErrors.push(errors[field]);
        }

        if (generalErrors.length && errorsBox) {
            ModalHelpers.showGeneralError(errorsBox, generalErrors.join(". "));
        }
    };

    /**
     * Настроить автоматический сброс формы и ошибок при закрытии модалки.
     * Вешает MutationObserver на атрибут hidden. Безопасен при повторном вызове —
     * если Observer уже установлен, ничего не делает.
     *
     * @param {HTMLElement} modal    — .modal-overlay
     * @param {Function}   [callback] — дополнительный колбэк при закрытии
     */
    ModalHelpers.setupResetOnClose = function (modal, callback) {
        if (modal._modalResetObserver) return;

        var observer = new MutationObserver(function (mutations) {
            for (var i = 0; i < mutations.length; i++) {
                if (mutations[i].attributeName === "hidden" && modal.hidden) {
                    var form = modal.querySelector("form");
                    if (form) form.reset();
                    ModalHelpers.clearErrors(modal);

                    var submitBtn = modal.querySelector("[type='submit']");
                    if (submitBtn) {
                        ModalHelpers.setSubmitting(submitBtn, false);
                    }

                    if (typeof callback === "function") callback(modal);
                    break;
                }
            }
        });

        observer.observe(modal, { attributes: true, attributeFilter: ["hidden"] });
        modal._modalResetObserver = true;
    };

    /**
     * Переключить кнопку в состояние загрузки / обратно.
     * Хранит оригинальный HTML в btn._originalHTML.
     *
     * @param {HTMLElement} btn       — элемент кнопки
     * @param {boolean}     isLoading — true = загрузка, false = восстановить
     */
    ModalHelpers.setSubmitting = function (btn, isLoading) {
        if (!btn) return;

        if (isLoading) {
            if (!btn._originalHTML) {
                btn._originalHTML = btn.innerHTML;
            }
            btn.disabled = true;
            btn.classList.add("is-loading");
            var loadingText = btn.dataset.loadingText || "Сохранение...";
            btn.textContent = loadingText;
        } else {
            btn.disabled = false;
            btn.classList.remove("is-loading");
            if (btn._originalHTML) {
                btn.innerHTML = btn._originalHTML;
                btn._originalHTML = null;
            }
        }
    };

    /**
     * Экранировать HTML-спецсимволы для безопасной вставки через innerHTML.
     *
     * @param {string} str — исходная строка
     * @returns {string} экранированная строка
     */
    ModalHelpers.escapeHtml = function (str) {
        var div = document.createElement("div");
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    };

    window.ModalHelpers = ModalHelpers;
})();
