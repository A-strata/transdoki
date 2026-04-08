document.addEventListener("DOMContentLoaded", function () {
    var statusSelect = document.querySelector("[data-filter-status]");
    var overdueCheckbox = document.querySelector("[data-filter-overdue]");

    function applyFilters() {
        var params = new URLSearchParams(window.location.search);
        var status = statusSelect ? statusSelect.value : "";
        var overdue = overdueCheckbox ? overdueCheckbox.checked : false;

        if (status) {
            params.set("status", status);
        } else {
            params.delete("status");
        }

        if (overdue) {
            params.set("overdue", "1");
        } else {
            params.delete("overdue");
        }

        params.delete("page");
        window.location.search = params.toString();
    }

    if (statusSelect) {
        statusSelect.addEventListener("change", applyFilters);
    }
    if (overdueCheckbox) {
        overdueCheckbox.addEventListener("change", applyFilters);
    }
});
