(function () {
    "use strict";

    var searchInput = document.querySelector("[data-search-input]");
    var clearBtn = document.querySelector("[data-search-clear]");
    var pageSizeSelect = document.querySelector("[data-page-size-select]");

    if (!searchInput) return;

    var debounceTimer;

    function buildUrl(params) {
        var url = new URL(window.location.pathname, window.location.origin);
        var keys = Object.keys(params);
        for (var i = 0; i < keys.length; i++) {
            if (params[keys[i]]) {
                url.searchParams.set(keys[i], params[keys[i]]);
            }
        }
        return url.toString();
    }

    function getCurrentParams() {
        var params = new URLSearchParams(window.location.search);
        return {
            q: searchInput.value.trim(),
            sort: params.get("sort") || "",
            dir: params.get("dir") || "",
            page_size: params.get("page_size") || "",
        };
    }

    function navigateWithParams(overrides) {
        var base = getCurrentParams();
        var keys = Object.keys(overrides);
        for (var i = 0; i < keys.length; i++) {
            base[keys[i]] = overrides[keys[i]];
        }
        window.location.href = buildUrl(base);
    }

    searchInput.addEventListener("input", function () {
        clearTimeout(debounceTimer);
        clearBtn.hidden = !this.value;
        debounceTimer = setTimeout(function () {
            navigateWithParams({ q: searchInput.value.trim() });
        }, 200);
    });

    if (clearBtn) {
        clearBtn.addEventListener("click", function () {
            searchInput.value = "";
            clearBtn.hidden = true;
            navigateWithParams({ q: "" });
        });
    }

    if (pageSizeSelect) {
        pageSizeSelect.addEventListener("change", function () {
            navigateWithParams({ page_size: this.value });
        });
    }
})();
