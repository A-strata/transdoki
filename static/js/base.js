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
