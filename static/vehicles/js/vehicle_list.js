(function () {
    "use strict";

    var contentContainer = document.querySelector("[data-list-content]");
    if (!contentContainer) return;

    var currentController = null;

    // ── Helpers ───────────────────────────────────────────────────────────

    function getParams() {
        var params = new URLSearchParams(window.location.search);
        return {
            type: params.get("type") || "",
            page_size: params.get("page_size") || "",
            page: params.get("page") || "",
        };
    }

    function buildSearch(overrides) {
        var params = getParams();
        var keys = Object.keys(overrides);
        for (var i = 0; i < keys.length; i++) {
            params[keys[i]] = overrides[keys[i]];
        }
        var search = new URLSearchParams();
        var pkeys = Object.keys(params);
        for (var j = 0; j < pkeys.length; j++) {
            if (params[pkeys[j]]) {
                search.set(pkeys[j], params[pkeys[j]]);
            }
        }
        var str = search.toString();
        return str ? "?" + str : "";
    }

    // ── Fetch + DOM replace ──────────────────────────────────────────────

    function loadContent(queryString, pushHistory) {
        if (currentController) {
            currentController.abort();
        }
        currentController = new AbortController();

        var url = window.location.pathname + queryString;

        fetch(url, {
            headers: { "X-Requested-With": "XMLHttpRequest" },
            signal: currentController.signal,
        })
            .then(function (response) {
                if (!response.ok) throw new Error(response.status);
                return response.text();
            })
            .then(function (html) {
                contentContainer.innerHTML = html;
                bindContentEvents();
                if (pushHistory) {
                    history.pushState({ queryString: queryString }, "", url);
                }
            })
            .catch(function (err) {
                if (err.name !== "AbortError") {
                    window.location.href = url;
                }
            });
    }

    // ── Filter chips ─────────────────────────────────────────────────────

    function bindFilterChips() {
        document.querySelectorAll(".filter-chip").forEach(function (chip) {
            chip.addEventListener("click", function (e) {
                e.preventDefault();
                var href = this.getAttribute("href");
                var chipParams = new URLSearchParams(href.split("?")[1] || "");
                var type = chipParams.get("type") || "";
                if (type === "all") type = "";

                document.querySelectorAll(".filter-chip").forEach(function (c) {
                    c.classList.remove("active");
                });
                this.classList.add("active");

                var qs = buildSearch({ type: type, page: "" });
                loadContent(qs, true);
            });
        });
    }

    bindFilterChips();

    // ── Delegated events (pagination, page-size) ─────────────────────────

    function bindContentEvents() {
        contentContainer.querySelectorAll(".pagination-link:not(.is-current):not(.is-disabled)").forEach(function (link) {
            link.addEventListener("click", function (e) {
                e.preventDefault();
                var href = this.getAttribute("href");
                loadContent(href, true);
            });
        });

        var pageSizeSelect = contentContainer.querySelector("[data-page-size-select]");
        if (pageSizeSelect) {
            pageSizeSelect.addEventListener("change", function () {
                var qs = buildSearch({ page_size: this.value, page: "" });
                loadContent(qs, true);
            });
        }
    }

    bindContentEvents();

    // ── History: «Назад» / «Вперёд» ──────────────────────────────────────

    window.addEventListener("popstate", function () {
        var qs = window.location.search;
        var params = new URLSearchParams(qs);
        var currentType = params.get("type") || "all";

        document.querySelectorAll(".filter-chip").forEach(function (chip) {
            var chipHref = chip.getAttribute("href");
            var chipType = new URLSearchParams(chipHref.split("?")[1] || "").get("type") || "all";
            chip.classList.toggle("active", chipType === currentType);
        });

        loadContent(qs, false);
    });
})();
