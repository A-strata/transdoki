/**
 * Страница «Мой тариф»: апгрейд/даунгрейд/отмена даунгрейда.
 *
 * Все операции — AJAX через CSRF token. При InsufficientFunds (HTTP 402)
 * открывается модалка с призывом пополнить баланс на нужную сумму, а не
 * сырая ошибка (см. ТЗ §7.6).
 */
(function () {
    "use strict";

    var page = document.querySelector(".subscription-page");
    if (!page) return;

    var urlUpgrade = page.dataset.urlUpgrade;
    var urlScheduleDowngrade = page.dataset.urlScheduleDowngrade;
    var urlCancelDowngrade = page.dataset.urlCancelDowngrade;
    var urlDeposit = page.dataset.urlDeposit;

    // ── Прогресс-бары: width в процентах, но не больше 100% ─────────
    document.querySelectorAll(".sub-progress-bar[data-current][data-limit]").forEach(function (bar) {
        var current = parseFloat(bar.dataset.current) || 0;
        var limit = parseFloat(bar.dataset.limit) || 0;
        if (limit <= 0) return;
        if (bar.classList.contains("is-overage")) {
            bar.style.width = "100%";
            return;
        }
        var pct = Math.min(100, (current / limit) * 100);
        bar.style.width = pct + "%";
        // 70% — жёлтый, ближе к 100 — без изменений (стиль уже может быть overage)
        if (pct >= 70 && !bar.classList.contains("is-warn")) {
            bar.classList.add("is-warn");
        }
    });

    // ── Утилита: CSRF из cookie ─────────────────────────────────────
    function getCsrf() {
        var m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : "";
    }

    // ── Утилита: отправка POST с CSRF ───────────────────────────────
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

    // ── Выбор плана в модалке смены тарифа ──────────────────────────
    document.querySelectorAll("[data-select-plan]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var option = btn.closest(".sub-plan-option");
            var planCode = option.dataset.planCode;
            var newPrice = parseFloat(option.dataset.planPrice) || 0;
            var currentPrice = parseFloat(option.dataset.currentPrice) || 0;
            var planName = option.querySelector("strong").textContent;

            if (newPrice > currentPrice) {
                handleUpgrade(planCode, planName);
            } else if (newPrice < currentPrice) {
                handleScheduleDowngrade(planCode, planName);
            } else {
                // Цены равны — теоретически невозможно, план ведь не тот же
                showError("Нельзя перейти на план с той же ценой.");
            }
        });
    });

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
                // Недостаточно средств — модалка с предложением пополнить
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
        var planNameEl = document.getElementById("ifm-plan-name");
        var requiredEl = document.getElementById("ifm-required");
        var balanceEl = document.getElementById("ifm-balance");
        var depositLink = document.getElementById("ifm-deposit-link");
        var modal = document.getElementById("insufficient-funds-modal");

        if (!modal) return;

        planNameEl.textContent = planName;
        requiredEl.textContent = body.required || "—";
        balanceEl.textContent = body.balance || "0";

        // Ссылка на пополнение с предзаполненной суммой (если known required)
        if (body.required) {
            // Округлим вверх до целого для UX удобства
            var amount = Math.ceil(parseFloat(body.required));
            depositLink.href = urlDeposit + "?amount=" + amount;
        } else {
            depositLink.href = urlDeposit;
        }

        // Закрываем модалку смены тарифа, открываем эту
        var planModal = document.getElementById("plan-change-modal");
        if (planModal) planModal.hidden = true;
        modal.hidden = false;
    }

    // ── Показать ошибку в модалке смены тарифа ──────────────────────
    function showError(msg) {
        var errBox = document.getElementById("plan-change-errors");
        if (errBox) {
            errBox.textContent = msg;
            errBox.hidden = false;
        } else {
            alert(msg);
        }
    }
})();
