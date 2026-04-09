(function () {
    "use strict";

    var searchWrap = document.querySelector(".search-field-wrap");
    var searchInput = document.querySelector("[data-search-input]");
    var clearBtn = document.querySelector("[data-search-clear]");
    var contentContainer = document.querySelector("[data-list-content]");

    if (!searchInput || !contentContainer) return;

    var debounceTimer;
    var currentController = null;

    function updateSearchState() {
        if (!searchWrap) return;
        searchWrap.classList.toggle("is-filtered", !!searchInput.value);
    }

    updateSearchState();

    // ── Helpers ───────────────────────────────────────────────────────────

    function getParams() {
        var params = new URLSearchParams(window.location.search);
        return {
            q: params.get("q") || "",
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
                    // Fallback — полная навигация при ошибке
                    window.location.href = url;
                }
            });
    }

    // ── Search ───────────────────────────────────────────────────────────

    searchInput.addEventListener("input", function () {
        clearTimeout(debounceTimer);
        updateSearchState();
        var value = this.value.trim();
        debounceTimer = setTimeout(function () {
            var qs = buildSearch({ q: value, page: "" });
            loadContent(qs, true);
        }, 300);
    });

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

    // ── Delegated events (sort, pagination, page-size) ───────────────────

    function bindContentEvents() {
        // Sort headers
        contentContainer.querySelectorAll(".sortable-header").forEach(function (link) {
            link.addEventListener("click", function (e) {
                e.preventDefault();
                var href = this.getAttribute("href");
                loadContent(href, true);
            });
        });

        // Pagination links
        contentContainer.querySelectorAll(".pagination-link:not(.is-current):not(.is-disabled)").forEach(function (link) {
            link.addEventListener("click", function (e) {
                e.preventDefault();
                var href = this.getAttribute("href");
                loadContent(href, true);
            });
        });

        // Page-size select
        var pageSizeSelect = contentContainer.querySelector("[data-page-size-select]");
        if (pageSizeSelect) {
            pageSizeSelect.addEventListener("change", function () {
                var qs = buildSearch({ page_size: this.value, page: "" });
                loadContent(qs, true);
            });
        }
    }

    bindContentEvents();

    // ── History: кнопка «Назад» / «Вперёд» ──────────────────────────────

    window.addEventListener("popstate", function (e) {
        var qs = window.location.search;
        // Обновляем поле поиска из URL
        var params = new URLSearchParams(qs);
        searchInput.value = params.get("q") || "";
        updateSearchState();
        loadContent(qs, false);
    });
})();
