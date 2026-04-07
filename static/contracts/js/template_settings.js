document.addEventListener("DOMContentLoaded", function () {
    // File upload triggers
    document.querySelectorAll(".template-upload-form .upload-trigger").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var form = btn.closest(".template-upload-form");
            var input = form.querySelector('input[type="file"]');
            input.click();
        });
    });

    document.querySelectorAll('.template-upload-form input[type="file"]').forEach(function (input) {
        input.addEventListener("change", function () {
            if (input.files.length > 0) {
                input.closest("form").submit();
            }
        });
    });

    // Copy placeholder to clipboard
    document.querySelectorAll("[data-copy-text]").forEach(function (chip) {
        chip.addEventListener("click", function () {
            var text = "{{ " + chip.dataset.copyText + " }}";
            navigator.clipboard.writeText(text).then(function () {
                chip.classList.add("copied");
                setTimeout(function () {
                    chip.classList.remove("copied");
                }, 1500);
            });
        });
    });
});
