document.addEventListener("DOMContentLoaded", function () {
    function hideFlash(el) {
        if (!el || el.classList.contains("is-hiding")) return;
        el.classList.add("is-hiding");
        setTimeout(function () { el.remove(); }, 240);
    }

    document.querySelectorAll(".flash").forEach(function (flash) {
        const closeBtn = flash.querySelector(".flash-close");
        if (closeBtn) {
            closeBtn.addEventListener("click", function () { hideFlash(flash); });
        }
        if (flash.dataset.autohide === "1") {
            setTimeout(function () { hideFlash(flash); }, 4500);
        }
    });

    /* ── Inline-подтверждение [data-confirm] ── */
    document.addEventListener("click", function (e) {
        var trigger = e.target.closest("[data-confirm-trigger]");
        if (trigger) {
            var wrap = trigger.closest("[data-confirm]");
            if (wrap) {
                trigger.hidden = true;
                var prompt = wrap.querySelector(".confirm-inline-prompt");
                if (prompt) prompt.hidden = false;
            }
            return;
        }

        var cancel = e.target.closest("[data-confirm-cancel]");
        if (cancel) {
            var wrap = cancel.closest("[data-confirm]");
            if (wrap) {
                var prompt = wrap.querySelector(".confirm-inline-prompt");
                if (prompt) prompt.hidden = true;
                var trigger = wrap.querySelector("[data-confirm-trigger]");
                if (trigger) trigger.hidden = false;
            }
        }
    });

    /* ── Форматирование госномера ТС ── */
    function formatGrn(grn, type) {
        if (type === "trailer") {
            return grn.replace(/^([А-ЯA-Z]{2})(\d{4})(\d{2,3})$/i, "$1 $2 $3");
        }
        return grn.replace(/^([А-ЯA-Z])(\d{3})([А-ЯA-Z]{2})(\d{2,3})$/i, "$1 $2 $3 $4");
    }

    /* ── Модальные окна [data-modal-open] / [data-modal-close] ── */
    document.addEventListener("click", function (e) {
        var opener = e.target.closest("[data-modal-open]");
        if (opener) {
            var modal = document.getElementById(opener.dataset.modalOpen);
            if (modal) {
                var nameEl = modal.querySelector("#delete-vehicle-name");
                if (nameEl) {
                    var grn = opener.dataset.deleteGrn || "";
                    var type = opener.dataset.deleteType || "";
                    var brand = opener.dataset.deleteBrand || "";
                    var formatted = formatGrn(grn, type);
                    nameEl.textContent = formatted + (brand ? ", " + brand : "");
                }
                var form = modal.querySelector("form");
                if (form && opener.dataset.deleteUrl) {
                    form.action = opener.dataset.deleteUrl;
                }
                modal.hidden = false;
            }
            return;
        }

        var closer = e.target.closest("[data-modal-close]");
        if (closer) {
            var modal = closer.closest(".modal-overlay");
            if (modal) modal.hidden = true;
            return;
        }

        /* Клик по overlay (за пределами dialog) закрывает модал */
        if (e.target.classList.contains("modal-overlay")) {
            e.target.hidden = true;
        }
    });

    /* Escape закрывает модал */
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") {
            var modal = document.querySelector(".modal-overlay:not([hidden])");
            if (modal) modal.hidden = true;
        }
    });

    document.querySelectorAll("form").forEach(function (form) {
        form.addEventListener("submit", function () {
            const btn = form.querySelector("[data-loading-text]");
            if (!btn) return;
            btn.disabled = true;
            btn.classList.add("is-loading");
            btn.textContent = btn.dataset.loadingText;
        });
    });
});
