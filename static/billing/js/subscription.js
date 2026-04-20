/**
 * Страница «Мой тариф»: апгрейд/даунгрейд/отмена даунгрейда.
 *
 * Все операции — AJAX через CSRF token. Подтверждения и результаты — через
 * стилизованные модалки (паттерн .modal-overlay + data-modal-* из base.js).
 * Нативные confirm()/alert() не используются — ui-guide §4.
 */
(function () {
    "use strict";

    var page = document.querySelector(".subscription-page");
    if (!page) return;

    var urlUpgrade = page.dataset.urlUpgrade;
    var urlScheduleDowngrade = page.dataset.urlScheduleDowngrade;
    var urlCancelDowngrade = page.dataset.urlCancelDowngrade;
    var urlDeposit = page.dataset.urlDeposit;
    var currentPeriodEnd = page.dataset.currentPeriodEnd || "";

    // ── Прогресс-бары (.lk-progress > span) ─────────────────────────
    document.querySelectorAll(".lk-progress > span[data-current][data-limit]").forEach(function (fill) {
        var current = parseFloat(fill.dataset.current) || 0;
        var limit = parseFloat(fill.dataset.limit) || 0;
        if (limit <= 0) return;
        var pct = Math.min(100, (current / limit) * 100);
        fill.style.width = pct + "%";
        var bar = fill.parentElement;
        if (current > limit) {
            bar.classList.add("is-danger");
        } else if (pct >= 80 && !bar.classList.contains("is-danger")) {
            bar.classList.add("is-warn");
        }
    });

    // ── CSRF + fetch helpers ────────────────────────────────────────
    function getCsrf() {
        var m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : "";
    }

    function postJson(url, data) {
        var body = new URLSearchParams(data);
        return fetch(url, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCsrf(),
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: body.toString(),
        }).then(function (resp) {
            return resp.json().then(function (body) {
                return { ok: resp.ok, status: resp.status, body: body };
            });
        });
    }

    // ── Работа с модалками ──────────────────────────────────────────
    function openModal(id) {
        var modal = document.getElementById(id);
        if (modal) modal.hidden = false;
        return modal;
    }

    function closeModal(id) {
        var modal = document.getElementById(id);
        if (modal) modal.hidden = true;
    }

    function setText(modal, selector, text) {
        modal.querySelectorAll(selector).forEach(function (el) {
            el.textContent = text;
        });
    }

    function setButtonLoading(btn, isLoading) {
        if (!btn) return;
        if (isLoading) {
            if (!btn.dataset.originalText) {
                btn.dataset.originalText = btn.textContent;
            }
            btn.disabled = true;
            btn.textContent = btn.dataset.loadingText || "Подождите…";
        } else {
            btn.disabled = false;
            if (btn.dataset.originalText) {
                btn.textContent = btn.dataset.originalText;
                delete btn.dataset.originalText;
            }
        }
    }

    // Сброс disabled на всех confirm-кнопках при закрытии модалки
    document.querySelectorAll(".modal-overlay").forEach(function (modal) {
        new MutationObserver(function () {
            if (modal.hidden) {
                modal.querySelectorAll("button[data-confirm-upgrade], button[data-confirm-schedule-downgrade], button[data-confirm-cancel-downgrade]").forEach(function (btn) {
                    setButtonLoading(btn, false);
                });
            }
        }).observe(modal, { attributes: true, attributeFilter: ["hidden"] });
    });

    // ── Выбор плана (1) из модалки и (2) из сетки планов ───────────
    // Оба триггера приводят к общему обработчику handlePlanSelection.
    document.querySelectorAll("[data-select-plan]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var option = btn.closest(".sub-plan-option");
            handlePlanSelection({
                planCode: option.dataset.planCode,
                planName: option.dataset.planName || option.querySelector("strong").textContent,
                newPrice: parseFloat(option.dataset.planPrice) || 0,
                currentPrice: parseFloat(option.dataset.currentPrice) || 0,
            });
        });
    });

    document.querySelectorAll("[data-plan-select]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            handlePlanSelection({
                planCode: btn.dataset.planSelect,
                planName: btn.dataset.planName || "",
                newPrice: parseFloat(btn.dataset.planPrice) || 0,
                currentPrice: parseFloat(btn.dataset.currentPrice) || 0,
            });
        });
    });

    function handlePlanSelection(opts) {
        if (opts.newPrice > opts.currentPrice) {
            openUpgradeConfirm(opts.planCode, opts.planName);
        } else if (opts.newPrice < opts.currentPrice) {
            openDowngradeConfirm(opts.planCode, opts.planName);
        } else {
            showError("Нельзя перейти на план с той же ценой.");
        }
    }

    // ── Апгрейд: открытие модалки подтверждения ─────────────────────
    function openUpgradeConfirm(planCode, planName) {
        var modal = openModal("upgrade-confirm-modal");
        if (!modal) return;
        setText(modal, "[data-plan-name]", planName);
        var confirmBtn = modal.querySelector("[data-confirm-upgrade]");
        confirmBtn.dataset.planCode = planCode;
        confirmBtn.dataset.planName = planName;
    }

    document.querySelectorAll("[data-confirm-upgrade]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            submitUpgrade(btn.dataset.planCode, btn.dataset.planName, btn);
        });
    });

    function submitUpgrade(planCode, planName, btn) {
        setButtonLoading(btn, true);
        postJson(urlUpgrade, { plan_code: planCode }).then(function (result) {
            closeModal("upgrade-confirm-modal");
            if (result.ok && result.body.ok) {
                showUpgradeSuccess(planName, result.body.charged);
                return;
            }
            if (result.status === 402) {
                showInsufficientFunds(planName, result.body);
                return;
            }
            showError(result.body.error || "Ошибка смены тарифа");
        }).catch(function () {
            closeModal("upgrade-confirm-modal");
            showError("Сетевая ошибка. Попробуйте ещё раз.");
        });
    }

    function showUpgradeSuccess(planName, charged) {
        var modal = openModal("upgrade-success-modal");
        if (!modal) return;
        setText(modal, "[data-plan-name]", planName);
        setText(modal, "[data-charged]", formatMoney(charged));
    }

    // ── Даунгрейд: открытие модалки подтверждения ───────────────────
    function openDowngradeConfirm(planCode, planName) {
        var modal = openModal("downgrade-schedule-confirm-modal");
        if (!modal) return;
        setText(modal, "[data-plan-name]", planName);
        setText(modal, "[data-current-period-end]", currentPeriodEnd || "конца текущего периода");
        var confirmBtn = modal.querySelector("[data-confirm-schedule-downgrade]");
        confirmBtn.dataset.planCode = planCode;
        confirmBtn.dataset.planName = planName;
    }

    document.querySelectorAll("[data-confirm-schedule-downgrade]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            submitScheduleDowngrade(btn.dataset.planCode, btn.dataset.planName, btn);
        });
    });

    function submitScheduleDowngrade(planCode, planName, btn) {
        setButtonLoading(btn, true);
        postJson(urlScheduleDowngrade, { plan_code: planCode }).then(function (result) {
            closeModal("downgrade-schedule-confirm-modal");
            if (result.ok && result.body.ok) {
                showDowngradeSuccess(planName, result.body);
                return;
            }
            showError(result.body.error || "Ошибка планирования даунгрейда");
        }).catch(function () {
            closeModal("downgrade-schedule-confirm-modal");
            showError("Сетевая ошибка. Попробуйте ещё раз.");
        });
    }

    function showDowngradeSuccess(planName, body) {
        var modal = openModal("downgrade-schedule-success-modal");
        if (!modal) return;
        setText(modal, "[data-plan-name]", planName);
        setText(modal, "[data-effective-at]", formatIsoDate(body.effective_at));

        var warningsBox = modal.querySelector(".sub-downgrade-warnings");
        var warningsList = modal.querySelector("[data-warnings-list]");
        warningsList.innerHTML = "";
        var warnings = body.warnings;
        if (Array.isArray(warnings) && warnings.length) {
            warnings.forEach(function (w) {
                var li = document.createElement("li");
                li.textContent = w;
                warningsList.appendChild(li);
            });
            warningsBox.hidden = false;
        } else {
            warningsBox.hidden = true;
        }
    }

    // ── Отмена запланированного даунгрейда ──────────────────────────
    var cancelBtn = document.querySelector("[data-cancel-downgrade]");
    if (cancelBtn) {
        cancelBtn.addEventListener("click", function () {
            openModal("cancel-downgrade-confirm-modal");
        });
    }

    document.querySelectorAll("[data-confirm-cancel-downgrade]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            setButtonLoading(btn, true);
            postJson(urlCancelDowngrade, {}).then(function (result) {
                closeModal("cancel-downgrade-confirm-modal");
                if (result.ok && result.body.ok) {
                    window.location.reload();
                    return;
                }
                showError(result.body.error || "Не удалось отменить переход");
            }).catch(function () {
                closeModal("cancel-downgrade-confirm-modal");
                showError("Сетевая ошибка. Попробуйте ещё раз.");
            });
        });
    });

    // ── Reload по клику на кнопку «Готово / Понятно» success-модалок
    document.querySelectorAll("[data-reload-on-close]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            window.location.reload();
        });
    });

    // ── Модалка «недостаточно средств» ──────────────────────────────
    function showInsufficientFunds(planName, body) {
        var modal = document.getElementById("insufficient-funds-modal");
        if (!modal) return;

        document.getElementById("ifm-plan-name").textContent = planName;
        document.getElementById("ifm-required").textContent = body.required || "—";
        document.getElementById("ifm-balance").textContent = body.balance || "0";

        var depositLink = document.getElementById("ifm-deposit-link");
        if (body.required) {
            var amount = Math.ceil(parseFloat(body.required));
            depositLink.href = urlDeposit + "?amount=" + amount;
        } else {
            depositLink.href = urlDeposit;
        }

        var planModal = document.getElementById("plan-change-modal");
        if (planModal) planModal.hidden = true;
        modal.hidden = false;
    }

    function showError(msg) {
        var errBox = document.getElementById("plan-change-errors");
        if (errBox) {
            errBox.textContent = msg;
            errBox.hidden = false;
        } else {
            showToast(msg);
        }
    }

    // ── Форматеры ───────────────────────────────────────────────────
    function formatMoney(value) {
        if (value === undefined || value === null || value === "") return "0";
        var num = parseFloat(value);
        if (isNaN(num)) return String(value);
        return num.toLocaleString("ru-RU", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    function formatIsoDate(iso) {
        if (!iso) return "—";
        var d = new Date(iso);
        if (isNaN(d.getTime())) return String(iso);
        return d.toLocaleDateString("ru-RU", {
            day: "numeric",
            month: "long",
            year: "numeric",
        });
    }

    // ── Копирование реквизитов ─────────────────────────────────────
    var copyBtn = document.querySelector("[data-copy-requisites]");
    if (copyBtn) {
        copyBtn.addEventListener("click", function () {
            var box = document.querySelector("[data-req-box]");
            if (!box) return;
            var pairs = [];
            var keys = box.querySelectorAll(".lk-req-key");
            keys.forEach(function (key) {
                var value = key.nextElementSibling;
                var keyText = (key.textContent || "").trim();
                var valueText = (value ? value.textContent : "").trim();
                if (keyText && valueText) {
                    pairs.push(keyText + ": " + valueText);
                }
            });
            var text = pairs.join("\n");
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(function () {
                    flashCopied(copyBtn);
                }).catch(function () {
                    flashCopied(copyBtn, "Не удалось скопировать");
                });
            } else {
                flashCopied(copyBtn, "Буфер обмена недоступен");
            }
        });
    }

    function flashCopied(btn, message) {
        var original = btn.dataset.originalHtml;
        if (!original) {
            btn.dataset.originalHtml = btn.innerHTML;
            original = btn.innerHTML;
        }
        btn.textContent = message || "Скопировано";
        setTimeout(function () {
            btn.innerHTML = original;
        }, 1600);
    }

    // ── Stub-toasts для кнопок «скоро» ─────────────────────────────
    document.querySelectorAll("[data-stub-toast]").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
            e.preventDefault();
            showToast(btn.dataset.stubToast);
        });
    });

    function showToast(text) {
        var wrap = document.querySelector(".flash-wrap");
        if (!wrap) {
            wrap = document.createElement("div");
            wrap.className = "flash-wrap";
            document.body.appendChild(wrap);
        }
        var flash = document.createElement("div");
        flash.className = "flash flash-info";
        flash.setAttribute("data-autohide", "1");
        flash.textContent = text;
        var close = document.createElement("button");
        close.type = "button";
        close.className = "flash-close";
        close.setAttribute("aria-label", "Закрыть");
        close.textContent = "×";
        close.addEventListener("click", function () { flash.remove(); });
        flash.appendChild(close);
        wrap.appendChild(flash);
        setTimeout(function () { flash.remove(); }, 4000);
    }
})();
