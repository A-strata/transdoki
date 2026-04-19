/**
 * Страница «Мой тариф»: апгрейд/даунгрейд/отмена даунгрейда.
 *
 * Все операции — AJAX через CSRF token. При InsufficientFunds (HTTP 402)
 * открывается модалка с призывом пополнить баланс на нужную сумму, а не
 * сырая ошибка.
 *
 * Логика смены тарифа не трогалась — только селекторы и триггеры переведены
 * на новый UI (.lk-plans + .sub-plans-list в модалке).
 */
(function () {
    "use strict";

    var page = document.querySelector(".subscription-page");
    if (!page) return;

    var urlUpgrade = page.dataset.urlUpgrade;
    var urlScheduleDowngrade = page.dataset.urlScheduleDowngrade;
    var urlCancelDowngrade = page.dataset.urlCancelDowngrade;
    var urlDeposit = page.dataset.urlDeposit;

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
            handleUpgrade(opts.planCode, opts.planName);
        } else if (opts.newPrice < opts.currentPrice) {
            handleScheduleDowngrade(opts.planCode, opts.planName);
        } else {
            showError("Нельзя перейти на план с той же ценой.");
        }
    }

    // ── Апгрейд ─────────────────────────────────────────────────────
    function handleUpgrade(planCode, planName) {
        if (!confirm("Перейти на тариф «" + planName + "»? Спишется pro rata-разница за оставшиеся дни.")) {
            return;
        }
        postJson(urlUpgrade, { plan_code: planCode }).then(function (result) {
            if (result.ok && result.body.ok) {
                alert("Тариф изменён. Списано: " + result.body.charged + " ₽.");
                window.location.reload();
                return;
            }
            if (result.status === 402) {
                showInsufficientFunds(planName, result.body);
                return;
            }
            showError(result.body.error || "Ошибка смены тарифа");
        }).catch(function () {
            showError("Сетевая ошибка. Попробуйте ещё раз.");
        });
    }

    // ── Даунгрейд ───────────────────────────────────────────────────
    function handleScheduleDowngrade(planCode, planName) {
        if (!confirm("Запланировать переход на тариф «" + planName + "»? Смена произойдёт в конце текущего периода.")) {
            return;
        }
        postJson(urlScheduleDowngrade, { plan_code: planCode }).then(function (result) {
            if (result.ok && result.body.ok) {
                var msg = "Переход на «" + planName + "» запланирован.";
                if (result.body.warnings && result.body.warnings.length) {
                    msg += "\n\nВажно:\n- " + result.body.warnings.join("\n- ");
                }
                alert(msg);
                window.location.reload();
                return;
            }
            showError(result.body.error || "Ошибка планирования даунгрейда");
        }).catch(function () {
            showError("Сетевая ошибка. Попробуйте ещё раз.");
        });
    }

    // ── Отмена запланированного даунгрейда ──────────────────────────
    var cancelBtn = document.querySelector("[data-cancel-downgrade]");
    if (cancelBtn) {
        cancelBtn.addEventListener("click", function () {
            if (!confirm("Отменить запланированный переход на другой тариф?")) return;
            postJson(urlCancelDowngrade, {}).then(function (result) {
                if (result.ok && result.body.ok) {
                    window.location.reload();
                    return;
                }
                showError(result.body.error || "Не удалось отменить переход");
            }).catch(function () {
                showError("Сетевая ошибка. Попробуйте ещё раз.");
            });
        });
    }

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
            alert(msg);
        }
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
            showStubToast(btn.dataset.stubToast);
        });
    });

    function showStubToast(text) {
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
