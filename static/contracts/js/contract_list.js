(function () {
    "use strict";

    var searchInput = document.querySelector("[data-search-input]");
    var clearBtn = document.querySelector("[data-search-clear]");
    var statusSelect = document.querySelector("[data-filter-status]");
    var contentContainer = document.querySelector("[data-list-content]");

    if (!contentContainer) return;

    var debounceTimer;
    var currentController = null;

    function updateSearchState() {
        if (!searchInput || !clearBtn) return;
        var hasValue = !!searchInput.value;
        clearBtn.hidden = !hasValue;
        searchInput.classList.toggle("is-filtered", hasValue);
    }

    updateSearchState();

    function getParams() {
        var params = new URLSearchParams(window.location.search);
        return {
            q: params.get("q") || "",
            status: params.get("status") || "",
            sort: params.get("sort") || "",
            dir: params.get("dir") || "",
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

    if (searchInput) {
        searchInput.addEventListener("input", function () {
            clearTimeout(debounceTimer);
            updateSearchState();
            var value = this.value.trim();
            debounceTimer = setTimeout(function () {
                var qs = buildSearch({ q: value, page: "" });
                loadContent(qs, true);
            }, 300);
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener("click", function () {
            searchInput.value = "";
            clearTimeout(debounceTimer);
            updateSearchState();
            var qs = buildSearch({ q: "", page: "" });
            loadContent(qs, true);
            searchInput.focus();
        });
    }

    if (statusSelect) {
        statusSelect.addEventListener("change", function () {
            var qs = buildSearch({ status: this.value, page: "" });
            loadContent(qs, true);
        });
    }

    function bindContentEvents() {
        contentContainer.querySelectorAll(".sortable-header").forEach(function (link) {
            link.addEventListener("click", function (e) {
                e.preventDefault();
                var href = this.getAttribute("href");
                loadContent(href, true);
            });
        });

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

    window.addEventListener("popstate", function () {
        var qs = window.location.search;
        var params = new URLSearchParams(qs);
        if (searchInput) searchInput.value = params.get("q") || "";
        if (statusSelect) statusSelect.value = params.get("status") || "";
        updateSearchState();
        loadContent(qs, false);
    });
})();
