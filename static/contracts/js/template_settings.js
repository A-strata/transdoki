document.addEventListener("DOMContentLoaded", function () {
    // ── Sidebar navigation ──
    var navItems = document.querySelectorAll(".tpl-nav-item");
    var panels = document.querySelectorAll(".tpl-panel");

    navItems.forEach(function (btn) {
        btn.addEventListener("click", function () {
            var target = btn.dataset.target;
            navItems.forEach(function (b) { b.removeAttribute("data-active"); });
            btn.setAttribute("data-active", "");
            panels.forEach(function (p) {
                p.hidden = p.dataset.panel !== target;
            });
        });
    });

    // ── Replace trigger (state A) ──
    document.querySelectorAll("[data-replace-trigger]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var form = btn.closest(".tpl-replace-form");
            form.querySelector("input[type=file]").click();
        });
    });

    document.querySelectorAll(".tpl-replace-form input[type=file]").forEach(function (input) {
        input.addEventListener("change", function () {
            if (input.files.length) input.closest("form").submit();
        });
    });

    // ── Confirm inline ──
    document.querySelectorAll("[data-confirm]").forEach(function (wrap) {
        var trigger = wrap.querySelector("[data-confirm-trigger]");
        var prompt = wrap.querySelector(".confirm-inline-prompt");
        var cancel = wrap.querySelector("[data-confirm-cancel]");

        trigger.addEventListener("click", function () {
            wrap.classList.add("is-confirming");
            prompt.hidden = false;
        });

        cancel.addEventListener("click", function () {
            wrap.classList.remove("is-confirming");
            prompt.hidden = true;
        });
    });

    // ── Upload zone (state B) ──
    document.querySelectorAll("[data-upload-zone]").forEach(function (zone) {
        var fileInput = zone.querySelector("input[type=file]");
        var stateIdle = zone.querySelector("[data-upload-state=idle]");
        var stateLoading = zone.querySelector("[data-upload-state=loading]");
        var stateError = zone.querySelector("[data-upload-state=error]");
        var filenameEl = zone.querySelector("[data-upload-filename]");
        var errorTextEl = zone.querySelector("[data-upload-error-text]");

        function showState(name) {
            stateIdle.hidden = name !== "idle";
            stateLoading.hidden = name !== "loading";
            stateError.hidden = name !== "error";
            zone.classList.remove("is-loading", "is-error");
            if (name === "loading") zone.classList.add("is-loading");
            if (name === "error") zone.classList.add("is-error");
        }

        zone.addEventListener("click", function (e) {
            if (zone.classList.contains("is-loading")) return;
            if (e.target.closest("button")) return;
            fileInput.click();
        });

        fileInput.addEventListener("change", function () {
            var file = fileInput.files[0];
            if (!file) return;

            if (!file.name.toLowerCase().endsWith(".docx")) {
                showState("error");
                errorTextEl.textContent = "Допускаются только файлы формата .docx";
                fileInput.value = "";
                return;
            }

            if (file.size > 5 * 1024 * 1024) {
                showState("error");
                errorTextEl.textContent = "Максимальный размер файла — 5 МБ";
                fileInput.value = "";
                return;
            }

            filenameEl.textContent = file.name;
            showState("loading");
            zone.submit();
        });
    });

    // ── Copy placeholder ──
    var toast = document.getElementById("tpl-toast");
    var toastTimer = null;

    function showToast(text) {
        toast.textContent = text;
        toast.hidden = false;
        requestAnimationFrame(function () {
            toast.classList.add("is-visible");
        });
        clearTimeout(toastTimer);
        toastTimer = setTimeout(function () {
            toast.classList.remove("is-visible");
            setTimeout(function () { toast.hidden = true; }, 200);
        }, 2000);
    }

    document.querySelectorAll("[data-copy-text]").forEach(function (chip) {
        chip.addEventListener("click", function () {
            var text = "{{ " + chip.dataset.copyText + " }}";
            navigator.clipboard.writeText(text).then(function () {
                chip.classList.add("is-copied");
                setTimeout(function () { chip.classList.remove("is-copied"); }, 1400);
                showToast("Скопировано: " + text);
            });
        });
    });
});
