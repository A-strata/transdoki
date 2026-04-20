/**
 * Личный кабинет — блок «Профиль и команда» (v1.3).
 *
 * Сборка флоу:
 *   initModals         — open/close, ESC, overlay click, focus trap.
 *                        closeModal() сбрасывает disabled и текст submit'ов
 *                        через data-submit-default-label — гарантия против
 *                        регрессии «кнопка работает один раз».
 *   initKebabMenus     — toggle, outside click, ESC.
 *                        openModal() форсирует closeAllKebabs(), чтобы меню
 *                        не оставалось поверх открытой модалки.
 *   initCredentialCopy — [data-copy] с fallback execCommand.
 *   showToast          — глобальная функция на window. Варианты:
 *                        default | error | success. БЕЗ undo (v1.3).
 *   initInviteFlow     — submit invite-form → success-step с credentials.
 *   initResetFlow      — chain reset-confirm → reset-success.
 *   initEditSelfFlow   — submit edit-self (только ФИО).
 *   initEditUserFlow   — submit edit-user (ФИО + роль одним POST'ом).
 *
 * Атрибуты: data-lk-modal-open / data-lk-modal-close (префикс lk-
 * обязателен — иначе пересечётся с base.js, который оперирует
 * .modal-overlay + hidden и сломает close-flow).
 */
(function () {
    "use strict";

    /* ─── CSRF + AJAX ────────────────────────────────────────── */

    function getCsrf() {
        var m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : "";
    }

    function ajaxPost(url, data) {
        var body = new URLSearchParams(data || {});
        return fetch(url, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCsrf(),
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: body.toString(),
        }).then(function (resp) {
            return resp.json().then(function (json) {
                return { ok: resp.ok, status: resp.status, body: json };
            }).catch(function () {
                return { ok: false, status: resp.status, body: {} };
            });
        });
    }

    /* ─── Toast ──────────────────────────────────────────────── */

    function getToastWrap() {
        var wrap = document.querySelector(".lk-toast-wrap");
        if (!wrap) {
            wrap = document.createElement("div");
            wrap.className = "lk-toast-wrap";
            wrap.setAttribute("aria-live", "polite");
            document.body.appendChild(wrap);
        }
        return wrap;
    }

    function showToast(message, opts) {
        opts = opts || {};
        var duration = typeof opts.duration === "number" ? opts.duration : 4500;
        var variant = opts.variant;

        var wrap = getToastWrap();
        var toast = document.createElement("div");
        toast.className = "lk-toast" + (variant ? " lk-toast--" + variant : "");
        toast.textContent = message;
        wrap.appendChild(toast);

        setTimeout(function () {
            toast.classList.add("is-hiding");
            setTimeout(function () {
                if (toast.parentNode) toast.parentNode.removeChild(toast);
            }, 220);
        }, duration);
    }

    window.showToast = showToast;

    /* ─── Modals ─────────────────────────────────────────────── */

    var FOCUSABLE = [
        "a[href]",
        "button:not([disabled])",
        "input:not([disabled])",
        "select:not([disabled])",
        "textarea:not([disabled])",
        "[tabindex]:not([tabindex='-1'])",
    ].join(",");

    var openStack = [];
    var lastTrigger = null;

    function openModal(id, trigger) {
        var modal = document.getElementById(id);
        if (!modal) return null;

        // Любой открытый kebab должен закрыться до показа модалки,
        // иначе меню остаётся позиционированным поверх содержимого
        // и перехватывает клики.
        closeAllKebabs();

        modal.classList.add("is-open");
        modal.setAttribute("aria-hidden", "false");

        // Первый шаг становится видимым, остальные скрыты.
        var steps = modal.querySelectorAll("[data-lk-modal-step]");
        if (steps.length > 0) {
            steps.forEach(function (step, i) { step.hidden = i !== 0; });
        }

        openStack.push(modal);
        lastTrigger = trigger || document.activeElement;

        var focusables = modal.querySelectorAll(FOCUSABLE);
        if (focusables.length > 0) {
            setTimeout(function () { focusables[0].focus(); }, 0);
        }
        return modal;
    }

    function resetSubmitButtonsInModal(modal) {
        modal.querySelectorAll("[data-submit-default-label]").forEach(function (btn) {
            btn.disabled = false;
            btn.textContent = btn.dataset.submitDefaultLabel;
        });
    }

    function clearFormStateInModal(modal) {
        modal.querySelectorAll("form").forEach(function (form) { form.reset(); });
        modal.querySelectorAll(".lk-field-input.is-invalid").forEach(function (el) {
            el.classList.remove("is-invalid");
        });
        modal.querySelectorAll(".lk-field-error").forEach(function (el) {
            el.textContent = "";
        });
        modal.querySelectorAll(".lk-form-errors").forEach(function (el) {
            el.textContent = "";
        });
        modal.querySelectorAll("[data-cred-value]").forEach(function (el) {
            el.textContent = "";
        });
    }

    function closeModal(modal) {
        if (!modal) return;
        modal.classList.remove("is-open");
        modal.setAttribute("aria-hidden", "true");

        clearFormStateInModal(modal);
        resetSubmitButtonsInModal(modal);

        var idx = openStack.indexOf(modal);
        if (idx > -1) openStack.splice(idx, 1);

        if (lastTrigger && typeof lastTrigger.focus === "function") {
            lastTrigger.focus();
        }
        lastTrigger = null;
    }

    function showStep(modal, stepName) {
        modal.querySelectorAll("[data-lk-modal-step]").forEach(function (step) {
            step.hidden = step.dataset.lkModalStep !== stepName;
        });
        var active = modal.querySelector("[data-lk-modal-step]:not([hidden])");
        if (active) {
            var focusable = active.querySelector(FOCUSABLE);
            if (focusable) focusable.focus();
        }
    }

    function initModals() {
        document.addEventListener("click", function (e) {
            var opener = e.target.closest("[data-lk-modal-open]");
            if (opener) {
                e.preventDefault();
                openModal(opener.dataset.lkModalOpen, opener);
                return;
            }
            var closer = e.target.closest("[data-lk-modal-close]");
            if (closer) {
                e.preventDefault();
                var modal = closer.closest(".lk-modal-overlay");
                if (modal) closeModal(modal);
                return;
            }
            // Клик по overlay-фону (не по модалке внутри) закрывает.
            if (e.target.classList && e.target.classList.contains("lk-modal-overlay")) {
                closeModal(e.target);
            }
        });

        // ESC — закрыть верхнюю модалку или открытое kebab.
        document.addEventListener("keydown", function (e) {
            if (e.key !== "Escape") return;
            var top = openStack[openStack.length - 1];
            if (top) {
                closeModal(top);
                e.stopPropagation();
                return;
            }
            var kebab = document.querySelector(".lk-kebab-menu:not([hidden])");
            if (kebab) closeKebabMenu(kebab);
        });

        // Focus trap — удержание Tab внутри верхней модалки.
        document.addEventListener("keydown", function (e) {
            if (e.key !== "Tab") return;
            var top = openStack[openStack.length - 1];
            if (!top) return;
            var focusables = Array.prototype.filter.call(
                top.querySelectorAll(FOCUSABLE),
                function (el) { return el.offsetParent !== null; }
            );
            if (focusables.length === 0) return;
            var first = focusables[0];
            var last = focusables[focusables.length - 1];
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        });
    }

    /* ─── Kebab menus ────────────────────────────────────────── */

    function closeKebabMenu(menu) {
        menu.hidden = true;
        var cell = menu.parentElement;
        var toggle = cell ? cell.querySelector(".lk-kebab") : null;
        if (toggle) toggle.setAttribute("aria-expanded", "false");
    }

    function closeAllKebabs() {
        document.querySelectorAll(".lk-kebab-menu:not([hidden])").forEach(closeKebabMenu);
    }

    function initKebabMenus() {
        document.addEventListener("click", function (e) {
            var toggle = e.target.closest(".lk-kebab");
            if (toggle) {
                var cell = toggle.closest(".lk-actions-cell");
                if (!cell) return;
                var menu = cell.querySelector(".lk-kebab-menu");
                if (!menu) return;
                var isOpen = !menu.hidden;
                closeAllKebabs();
                if (!isOpen) {
                    menu.hidden = false;
                    toggle.setAttribute("aria-expanded", "true");
                }
                e.stopPropagation();
                return;
            }
            // Клик по пункту меню — меню закроется нативно (если это
            // data-lk-modal-open, openModal сам вызовет closeAllKebabs).
            // Здесь обрабатываем клик вне меню:
            if (!e.target.closest(".lk-kebab-menu")) {
                closeAllKebabs();
            }
        });
    }

    /* ─── Copy credentials ───────────────────────────────────── */

    function copyText(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text);
        }
        return new Promise(function (resolve, reject) {
            try {
                var ta = document.createElement("textarea");
                ta.value = text;
                ta.setAttribute("readonly", "");
                ta.style.position = "fixed";
                ta.style.opacity = "0";
                document.body.appendChild(ta);
                ta.select();
                var ok = document.execCommand("copy");
                document.body.removeChild(ta);
                ok ? resolve() : reject(new Error("execCommand copy failed"));
            } catch (err) {
                reject(err);
            }
        });
    }

    function initCredentialCopy() {
        document.addEventListener("click", function (e) {
            var btn = e.target.closest("[data-copy]");
            if (!btn) return;
            var sel = btn.dataset.copy;
            var scope = btn.closest(".lk-cred-row, .lk-cred") || document;
            var target = sel ? scope.querySelector(sel) : null;
            if (!target) return;
            var text = (target.textContent || "").trim();
            if (!text) return;
            copyText(text).then(function () {
                btn.classList.add("is-copied");
                var orig = btn.dataset.copyDefaultLabel || btn.textContent;
                if (!btn.dataset.copyDefaultLabel) {
                    btn.dataset.copyDefaultLabel = orig;
                }
                btn.textContent = "Скопировано";
                setTimeout(function () {
                    btn.classList.remove("is-copied");
                    btn.textContent = btn.dataset.copyDefaultLabel;
                }, 1600);
            }).catch(function () {
                showToast("Не удалось скопировать", { variant: "error" });
            });
        });
    }

    /* ─── Form-errors helpers ────────────────────────────────── */

    function clearFormErrors(modal) {
        modal.querySelectorAll(".lk-field-input.is-invalid").forEach(function (el) {
            el.classList.remove("is-invalid");
        });
        modal.querySelectorAll(".lk-field-error").forEach(function (el) {
            el.textContent = "";
        });
        var summary = modal.querySelector(".lk-form-errors");
        if (summary) summary.textContent = "";
    }

    function applyFormErrors(modal, errors) {
        var summary = modal.querySelector(".lk-form-errors");
        var firstMsg = null;
        for (var field in errors) {
            if (!Object.prototype.hasOwnProperty.call(errors, field)) continue;
            var raw = errors[field];
            var text = "";
            if (Array.isArray(raw)) {
                text = raw.map(function (m) {
                    return typeof m === "string" ? m : (m && m.message) || "";
                }).filter(Boolean).join("; ");
            } else if (typeof raw === "string") {
                text = raw;
            }
            var input = modal.querySelector("[name='" + field + "']");
            var err = modal.querySelector(".lk-field-error[data-for='" + field + "']");
            if (input) input.classList.add("is-invalid");
            if (err) err.textContent = text;
            if (!firstMsg) firstMsg = text;
        }
        if (summary && firstMsg) summary.textContent = firstMsg;
    }

    function markSubmitLoading(submitBtn) {
        if (!submitBtn.dataset.submitDefaultLabel) {
            submitBtn.dataset.submitDefaultLabel = submitBtn.textContent;
        }
        submitBtn.disabled = true;
        submitBtn.textContent = submitBtn.dataset.loadingText || "Сохранение…";
    }

    function unmarkSubmitLoading(submitBtn) {
        submitBtn.disabled = false;
        if (submitBtn.dataset.submitDefaultLabel) {
            submitBtn.textContent = submitBtn.dataset.submitDefaultLabel;
        }
    }

    /* ─── DOM helpers для обновления строки команды ───────────── */

    function buildInitials(first, last, fallback) {
        var f = (first || "").trim().slice(0, 1).toUpperCase();
        var l = (last || "").trim().slice(0, 1).toUpperCase();
        var joined = f + l;
        if (joined) return joined;
        return (fallback || "").slice(0, 2).toUpperCase();
    }

    function buildFullName(first, last, fallback) {
        var name = [first, last].filter(Boolean).map(function (s) { return s.trim(); })
            .filter(Boolean).join(" ");
        return name || fallback || "";
    }

    /* ─── Invite flow ────────────────────────────────────────── */

    function initInviteFlow() {
        var form = document.getElementById("invite-form");
        if (!form) return;

        form.addEventListener("submit", function (e) {
            e.preventDefault();
            var modal = form.closest(".lk-modal-overlay");
            clearFormErrors(modal);
            var submitBtn = form.querySelector("[type=submit]");
            markSubmitLoading(submitBtn);

            var params = {};
            new FormData(form).forEach(function (v, k) { params[k] = v; });

            ajaxPost(form.dataset.url, params).then(function (result) {
                unmarkSubmitLoading(submitBtn);
                if (result.ok && result.body.ok) {
                    var login = result.body.username || "";
                    var pwd = result.body.temp_password || "";
                    var fullName = result.body.full_name || login;
                    var roleDisp = result.body.role || "";
                    modal.querySelector("[data-cred-value='login']").textContent = login;
                    modal.querySelector("[data-cred-value='password']").textContent = pwd;
                    var nameHost = modal.querySelector("[data-success-name]");
                    if (nameHost) nameHost.textContent = fullName;
                    var roleHost = modal.querySelector("[data-success-role]");
                    if (roleHost) roleHost.textContent = roleDisp;
                    showStep(modal, "success");
                    return;
                }
                if (result.status === 403) {
                    closeModal(modal);
                    showToast("Недостаточно прав для создания пользователей", { variant: "error" });
                    return;
                }
                if (result.body && result.body.errors) {
                    applyFormErrors(modal, result.body.errors);
                } else {
                    var summary = modal.querySelector(".lk-form-errors");
                    if (summary) summary.textContent = (result.body && result.body.error) || "Не удалось создать пользователя";
                }
            }).catch(function () {
                unmarkSubmitLoading(submitBtn);
                var summary = modal.querySelector(".lk-form-errors");
                if (summary) summary.textContent = "Сетевая ошибка. Попробуйте ещё раз.";
            });
        });

        // После success — «Готово» перезагружает страницу, чтобы новый
        // сотрудник появился в списке. Клиентское добавление строки —
        // следующая итерация (не ломает UX сейчас).
        var doneBtn = document.getElementById("invite-done");
        if (doneBtn) {
            doneBtn.addEventListener("click", function () { window.location.reload(); });
        }
    }

    /* ─── Edit-self flow ─────────────────────────────────────── */

    function initEditSelfFlow() {
        var form = document.getElementById("edit-self-form");
        if (!form) return;

        form.addEventListener("submit", function (e) {
            e.preventDefault();
            var modal = form.closest(".lk-modal-overlay");
            clearFormErrors(modal);
            var submitBtn = form.querySelector("[type=submit]");
            markSubmitLoading(submitBtn);

            var params = {};
            new FormData(form).forEach(function (v, k) { params[k] = v; });
            // role в self-case бэкенд игнорирует, но отправлять не будем —
            // поле в модалке read-only и в форме его нет.

            ajaxPost(form.dataset.url, params).then(function (result) {
                unmarkSubmitLoading(submitBtn);
                if (result.ok && result.body.ok) {
                    // Обновляем self-row: ФИО + инициалы аватара.
                    var first = result.body.first_name || "";
                    var last = result.body.last_name || "";
                    var fallback = form.dataset.fallbackName || "";
                    var selfRow = document.querySelector(".lk-team-row.is-self");
                    if (selfRow) {
                        var nameHost = selfRow.querySelector(".lk-team-name");
                        if (nameHost) {
                            // Сохраняем чип роли (первый .lk-role-chip внутри).
                            var chip = nameHost.querySelector(".lk-role-chip");
                            nameHost.textContent = buildFullName(first, last, fallback) + " ";
                            if (chip) nameHost.appendChild(chip);
                        }
                        var avatar = selfRow.querySelector(".lk-avatar");
                        if (avatar) avatar.textContent = buildInitials(first, last, fallback);
                    }
                    closeModal(modal);
                    showToast("Профиль обновлён", { variant: "success" });
                    return;
                }
                if (result.body && result.body.errors) {
                    applyFormErrors(modal, result.body.errors);
                } else {
                    var summary = modal.querySelector(".lk-form-errors");
                    if (summary) summary.textContent = (result.body && result.body.error) || "Не удалось сохранить";
                }
            }).catch(function () {
                unmarkSubmitLoading(submitBtn);
                var summary = modal.querySelector(".lk-form-errors");
                if (summary) summary.textContent = "Сетевая ошибка. Попробуйте ещё раз.";
            });
        });
    }

    /* ─── Edit-user flow (ФИО + роль одним POST'ом) ──────────── */

    function initEditUserFlow() {
        // Перед открытием edit-user-modal заполняем форму из data-* пункта меню.
        document.addEventListener("click", function (e) {
            var trigger = e.target.closest("[data-lk-modal-open='edit-user-modal']");
            if (!trigger) return;
            var modal = document.getElementById("edit-user-modal");
            if (!modal) return;
            var form = modal.querySelector("form");
            form.dataset.url = trigger.dataset.updateUrl || "";
            form.dataset.profileId = trigger.dataset.profileId || "";
            form.dataset.fallbackName = trigger.dataset.fullName || trigger.dataset.login || "";
            setField(form, "first_name", trigger.dataset.firstName || "");
            setField(form, "last_name", trigger.dataset.lastName || "");
            setField(form, "role", trigger.dataset.role || "");
            setField(form, "login_display", trigger.dataset.login || "");
        });

        var form = document.getElementById("edit-user-form");
        if (!form) return;

        form.addEventListener("submit", function (e) {
            e.preventDefault();
            var modal = form.closest(".lk-modal-overlay");
            clearFormErrors(modal);
            var submitBtn = form.querySelector("[type=submit]");
            markSubmitLoading(submitBtn);

            var params = {};
            new FormData(form).forEach(function (v, k) {
                if (k !== "login_display") params[k] = v;
            });

            var url = form.dataset.url;
            ajaxPost(url, params).then(function (result) {
                unmarkSubmitLoading(submitBtn);
                if (result.ok && result.body.ok) {
                    var pid = form.dataset.profileId;
                    updateTeamRowAfterEdit(pid, {
                        first_name: result.body.first_name || "",
                        last_name: result.body.last_name || "",
                        role_display: result.body.role_display || "",
                        role: params.role || "",
                        fallback: form.dataset.fallbackName || "",
                    });
                    closeModal(modal);
                    showToast("Пользователь обновлён", { variant: "success" });
                    return;
                }
                if (result.status === 403) {
                    closeModal(modal);
                    showToast("Недостаточно прав", { variant: "error" });
                    return;
                }
                if (result.body && result.body.errors) {
                    applyFormErrors(modal, result.body.errors);
                } else {
                    var summary = modal.querySelector(".lk-form-errors");
                    if (summary) summary.textContent = (result.body && result.body.error) || "Не удалось сохранить";
                }
            }).catch(function () {
                unmarkSubmitLoading(submitBtn);
                var summary = modal.querySelector(".lk-form-errors");
                if (summary) summary.textContent = "Сетевая ошибка. Попробуйте ещё раз.";
            });
        });
    }

    function setField(form, name, value) {
        var el = form.querySelector("[name='" + name + "']");
        if (el) el.value = value;
    }

    // После успешного edit-user: обновляем в строке ФИО, инициалы,
    // мета-строку (email · роль · статус) и data-role на строке +
    // data-role у kebab-пункта «Редактировать…» (чтобы следующее
    // открытие модалки подтянуло актуальную роль).
    function updateTeamRowAfterEdit(profileId, patch) {
        var row = document.querySelector(".lk-team-row[data-profile-id='" + profileId + "']");
        if (!row) return;

        var nameHost = row.querySelector(".lk-team-name");
        if (nameHost) {
            nameHost.textContent = buildFullName(patch.first_name, patch.last_name, patch.fallback);
        }
        var avatar = row.querySelector(".lk-avatar");
        if (avatar) {
            avatar.textContent = buildInitials(patch.first_name, patch.last_name, patch.fallback);
        }

        var info = row.querySelector(".lk-team-info");
        if (info && patch.role_display) {
            // Мета-строка: {email} · {роль} · {статус}. Статус не менялся —
            // берём существующий последний сегмент или его HTML-обёртку.
            var emailText = (info.dataset.email || "").trim();
            var statusHtml = (info.dataset.statusHtml || "").trim();
            var roleWord = patch.role_display.toLowerCase();
            info.innerHTML = "";
            if (emailText) info.appendChild(document.createTextNode(emailText + " · "));
            info.appendChild(document.createTextNode(roleWord + " · "));
            if (statusHtml) {
                var span = document.createElement("span");
                span.innerHTML = statusHtml;
                while (span.firstChild) info.appendChild(span.firstChild);
            }
        }

        if (patch.role) {
            row.dataset.role = patch.role;
            var editTrigger = row.querySelector("[data-lk-modal-open='edit-user-modal']");
            if (editTrigger) {
                editTrigger.dataset.role = patch.role;
                editTrigger.dataset.firstName = patch.first_name;
                editTrigger.dataset.lastName = patch.last_name;
                editTrigger.dataset.fullName = buildFullName(
                    patch.first_name, patch.last_name, patch.fallback,
                );
            }
            var resetTrigger = row.querySelector("[data-lk-modal-open='reset-confirm-modal']");
            if (resetTrigger) {
                resetTrigger.dataset.fullName = buildFullName(
                    patch.first_name, patch.last_name, patch.fallback,
                );
                resetTrigger.dataset.roleDisplay = patch.role_display;
            }
        }
    }

    /* ─── Reset-password flow ────────────────────────────────── */

    function initResetFlow() {
        document.addEventListener("click", function (e) {
            var trigger = e.target.closest("[data-lk-modal-open='reset-confirm-modal']");
            if (!trigger) return;
            var modal = document.getElementById("reset-confirm-modal");
            if (!modal) return;
            var form = modal.querySelector("form");
            form.dataset.url = trigger.dataset.resetUrl || "";
            form.dataset.profileId = trigger.dataset.profileId || "";
            form.dataset.fullName = trigger.dataset.fullName || "";
            form.dataset.roleDisplay = trigger.dataset.roleDisplay || "";
            var nameHost = modal.querySelector("[data-reset-name]");
            if (nameHost) nameHost.textContent = trigger.dataset.fullName || trigger.dataset.login || "";
        });

        var form = document.getElementById("reset-confirm-form");
        if (!form) return;

        form.addEventListener("submit", function (e) {
            e.preventDefault();
            var modal = form.closest(".lk-modal-overlay");
            clearFormErrors(modal);
            var submitBtn = form.querySelector("[type=submit]");
            markSubmitLoading(submitBtn);

            ajaxPost(form.dataset.url, {}).then(function (result) {
                unmarkSubmitLoading(submitBtn);
                if (result.ok && result.body.ok) {
                    var fullName = result.body.full_name || form.dataset.fullName || "";
                    var roleDisp = form.dataset.roleDisplay || "";
                    closeModal(modal);
                    var success = document.getElementById("reset-success-modal");
                    if (success) {
                        success.querySelector("[data-cred-value='login']").textContent = result.body.username || "";
                        success.querySelector("[data-cred-value='password']").textContent = result.body.temp_password || "";
                        var nameHost = success.querySelector("[data-success-name]");
                        if (nameHost) nameHost.textContent = fullName;
                        var roleHost = success.querySelector("[data-success-role]");
                        if (roleHost) roleHost.textContent = roleDisp;
                        openModal("reset-success-modal");
                    }
                    return;
                }
                var summary = modal.querySelector(".lk-form-errors");
                if (summary) summary.textContent = (result.body && result.body.error) || "Не удалось сбросить пароль";
            }).catch(function () {
                unmarkSubmitLoading(submitBtn);
                var summary = modal.querySelector(".lk-form-errors");
                if (summary) summary.textContent = "Сетевая ошибка. Попробуйте ещё раз.";
            });
        });
    }

    /* ─── Stub toasts ────────────────────────────────────────── */

    function initStubToasts() {
        document.querySelectorAll("[data-stub-toast]").forEach(function (btn) {
            btn.addEventListener("click", function (e) {
                e.preventDefault();
                showToast(btn.dataset.stubToast);
            });
        });
    }

    /* ─── Bootstrap ──────────────────────────────────────────── */

    function ready(fn) {
        if (document.readyState !== "loading") fn();
        else document.addEventListener("DOMContentLoaded", fn);
    }

    ready(function () {
        initModals();
        initKebabMenus();
        initCredentialCopy();
        initInviteFlow();
        initEditSelfFlow();
        initEditUserFlow();
        initResetFlow();
        initStubToasts();
    });
})();
