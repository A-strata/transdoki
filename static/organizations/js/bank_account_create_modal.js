document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("create-bank-account-form");
    if (!form) return;

    var errorsBox = document.getElementById("ba-errors");
    var submitBtn = form.querySelector('button[type="submit"]');
    var originalText = submitBtn.textContent;
    var suggestUrl = form.dataset.suggestUrl;

    // Search elements
    var searchWrap = document.getElementById("ba-search-wrap");
    var searchInput = document.getElementById("ba-search");
    var dropdown = document.getElementById("ba-suggest-dropdown");

    // Selected bank display
    var selectedWrap = document.getElementById("ba-selected-wrap");
    var selectedName = document.getElementById("ba-selected-name");
    var selectedDetails = document.getElementById("ba-selected-details");
    var changeBtn = document.getElementById("ba-change-bank");

    // Hidden fields
    var hiddenBic = document.getElementById("ba-bic");
    var hiddenBankName = document.getElementById("ba-bank-name");
    var hiddenCorrAccount = document.getElementById("ba-corr-account");

    // Spinner
    var spin = document.getElementById("ba-spin");

    // Manual fallback
    var manualWrap = document.getElementById("ba-manual-wrap");
    var manualToggle = document.getElementById("ba-manual-toggle");
    var manualToggleWrap = document.getElementById("ba-manual-toggle-wrap");
    var backToSearch = document.getElementById("ba-back-to-search");
    var manualBic = document.getElementById("ba-manual-bic");
    var manualBankName = document.getElementById("ba-manual-bank-name");
    var manualCorrAccount = document.getElementById("ba-manual-corr-account");

    var isManualMode = false;
    var debounceTimer = null;
    var activeIndex = -1;

    // ── Suggest dropdown ──

    function showDropdown(items) {
        dropdown.innerHTML = "";
        if (!items.length) {
            dropdown.classList.remove("visible");
            return;
        }
        items.forEach(function (item) {
            var el = document.createElement("div");
            el.className = "suggest-item";
            el.innerHTML =
                '<span class="suggest-item-title">' + escapeHtml(item.bank_name) + '</span>' +
                '<span class="suggest-item-sub">БИК ' + escapeHtml(item.bic) + '</span>';
            el.addEventListener("mousedown", function (e) {
                e.preventDefault();
                selectBank(item);
            });
            dropdown.appendChild(el);
        });
        activeIndex = -1;
        dropdown.classList.add("visible");
    }

    function escapeHtml(str) {
        var div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function selectBank(item) {
        hiddenBic.value = item.bic;
        hiddenBankName.value = item.bank_name;
        hiddenCorrAccount.value = item.corr_account;

        selectedName.textContent = item.bank_name;
        selectedDetails.textContent = "БИК " + item.bic + " · К/с " + item.corr_account;

        searchWrap.hidden = true;
        manualToggleWrap.hidden = true;
        selectedWrap.hidden = false;
        dropdown.classList.remove("visible");
        searchInput.value = "";
    }

    function resetBankSelection() {
        hiddenBic.value = "";
        hiddenBankName.value = "";
        hiddenCorrAccount.value = "";
        selectedWrap.hidden = true;
        searchWrap.hidden = false;
        manualToggleWrap.hidden = isManualMode;
        searchInput.value = "";
        searchInput.focus();
    }

    searchInput.addEventListener("input", function () {
        var q = searchInput.value.trim();
        clearTimeout(debounceTimer);
        if (spin) spin.classList.remove("active");
        dropdown.classList.remove("visible");

        if (q.length < 2) return;

        if (spin) spin.classList.add("active");
        debounceTimer = setTimeout(function () {
            fetch(suggestUrl + "?q=" + encodeURIComponent(q))
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (spin) spin.classList.remove("active");
                    showDropdown(data.suggestions || []);
                })
                .catch(function () {
                    if (spin) spin.classList.remove("active");
                    dropdown.classList.remove("visible");
                });
        }, 400);
    });

    searchInput.addEventListener("keydown", function (e) {
        var items = dropdown.querySelectorAll(".suggest-item");
        if (!items.length || !dropdown.classList.contains("visible")) return;

        if (e.key === "ArrowDown") {
            e.preventDefault();
            activeIndex = Math.min(activeIndex + 1, items.length - 1);
            items.forEach(function (el, i) { el.classList.toggle("is-active", i === activeIndex); });
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            activeIndex = Math.max(activeIndex - 1, 0);
            items.forEach(function (el, i) { el.classList.toggle("is-active", i === activeIndex); });
        } else if (e.key === "Enter") {
            e.preventDefault();
            if (activeIndex >= 0 && items[activeIndex]) {
                items[activeIndex].dispatchEvent(new Event("mousedown"));
            }
        }
    });

    searchInput.addEventListener("blur", function () {
        setTimeout(function () { dropdown.classList.remove("visible"); }, 150);
    });

    changeBtn.addEventListener("click", resetBankSelection);

    // ── Manual mode ──

    manualToggle.addEventListener("click", function () {
        isManualMode = true;
        searchWrap.hidden = true;
        manualToggleWrap.hidden = true;
        manualWrap.hidden = false;
    });

    backToSearch.addEventListener("click", function () {
        isManualMode = false;
        manualBic.value = "";
        manualBankName.value = "";
        manualCorrAccount.value = "";
        hiddenBic.value = "";
        hiddenBankName.value = "";
        hiddenCorrAccount.value = "";
        manualWrap.hidden = true;
        searchWrap.hidden = false;
        manualToggleWrap.hidden = false;
        searchInput.value = "";
        searchInput.focus();
    });

    function syncManualToHidden() {
        hiddenBic.value = manualBic.value.trim();
        hiddenBankName.value = manualBankName.value.trim();
        hiddenCorrAccount.value = manualCorrAccount.value.trim();
    }

    // ── Form submit ──

    var fieldMap = {
        bic: "ba-bic",
        bank_name: "ba-bank-name",
        corr_account: "ba-corr-account",
        account_num: "ba-account-num"
    };
    var manualFieldMap = {
        bic: "ba-manual-bic",
        bank_name: "ba-manual-bank-name",
        corr_account: "ba-manual-corr-account"
    };

    function clearErrors() {
        errorsBox.hidden = true;
        errorsBox.innerHTML = "";
        form.querySelectorAll(".modal-field-error").forEach(function (el) { el.remove(); });
        form.querySelectorAll(".is-invalid").forEach(function (el) { el.classList.remove("is-invalid"); });
    }

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        clearErrors();

        if (isManualMode) {
            syncManualToHidden();
        }

        submitBtn.disabled = true;
        submitBtn.textContent = "Сохранение...";

        var data = new FormData(form);
        data.append("owner_id", form.dataset.ownerId);

        fetch(form.dataset.url, {
            method: "POST",
            body: data,
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
            .then(function (resp) {
                return resp.json().then(function (body) { return { ok: resp.ok, body: body }; });
            })
            .then(function (result) {
                if (result.ok) {
                    window.location.reload();
                    return;
                }

                var errors = result.body.errors || {};
                var generalErrors = [];
                var targetMap = isManualMode ? manualFieldMap : fieldMap;

                for (var field in errors) {
                    var inputId = targetMap[field] || fieldMap[field];
                    if (inputId) {
                        var input = document.getElementById(inputId);
                        if (input && input.type !== "hidden") {
                            input.classList.add("is-invalid");
                            var errEl = document.createElement("p");
                            errEl.className = "modal-field-error";
                            errEl.textContent = errors[field];
                            input.parentNode.appendChild(errEl);
                            continue;
                        }
                    }
                    generalErrors.push(errors[field]);
                }

                if (generalErrors.length) {
                    errorsBox.textContent = generalErrors.join(". ");
                    errorsBox.hidden = false;
                }

                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            })
            .catch(function () {
                errorsBox.textContent = "Ошибка сети. Попробуйте ещё раз.";
                errorsBox.hidden = false;
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            });
    });

    // ── Reset on modal close ──

    var modal = document.getElementById("create-bank-account-modal");
    if (modal) {
        var observer = new MutationObserver(function (mutations) {
            mutations.forEach(function (m) {
                if (m.attributeName === "hidden" && modal.hidden) {
                    form.reset();
                    clearErrors();
                    hiddenBic.value = "";
                    hiddenBankName.value = "";
                    hiddenCorrAccount.value = "";
                    isManualMode = false;
                    searchWrap.hidden = false;
                    selectedWrap.hidden = true;
                    manualWrap.hidden = true;
                    manualToggleWrap.hidden = false;
                    dropdown.classList.remove("visible");
                    if (spin) spin.classList.remove("active");
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalText;
                }
            });
        });
        observer.observe(modal, { attributes: true });
    }
});
