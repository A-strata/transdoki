document.addEventListener("DOMContentLoaded", function () {
    // ── Редактирование банковского счёта ──

    var form = document.getElementById("edit-bank-account-form");
    if (!form) return;

    var modal = document.getElementById("edit-bank-account-modal");
    var errorsBox = document.getElementById("eba-errors");
    var submitBtn = form.querySelector('button[type="submit"]');
    var suggestUrl = form.dataset.suggestUrl;

    var hiddenId = document.getElementById("eba-id");
    var accountNumInput = document.getElementById("eba-account-num");
    var accountHint = document.getElementById("eba-account-hint");

    // Search
    var searchWrap = document.getElementById("eba-search-wrap");
    var searchInput = document.getElementById("eba-search");
    var dropdown = document.getElementById("eba-suggest-dropdown");
    var spin = document.getElementById("eba-spin");

    // Selected bank
    var selectedWrap = document.getElementById("eba-selected-wrap");
    var selectedName = document.getElementById("eba-selected-name");
    var selectedDetails = document.getElementById("eba-selected-details");
    var changeBtn = document.getElementById("eba-change-bank");

    // Hidden fields
    var hiddenBic = document.getElementById("eba-bic");
    var hiddenBankName = document.getElementById("eba-bank-name");
    var hiddenCorrAccount = document.getElementById("eba-corr-account");

    // Manual
    var manualWrap = document.getElementById("eba-manual-wrap");
    var manualToggle = document.getElementById("eba-manual-toggle");
    var backToSearch = document.getElementById("eba-back-to-search");
    var manualBic = document.getElementById("eba-manual-bic");
    var manualBankName = document.getElementById("eba-manual-bank-name");
    var manualCorrAccount = document.getElementById("eba-manual-corr-account");

    var isManualMode = false;
    var debounceTimer = null;
    var activeIndex = -1;
    var ACCOUNT_LENGTH = 20;

    // ── Populate modal from data-attributes ──

    document.addEventListener("click", function (e) {
        var btn = e.target.closest('[data-modal-open="edit-bank-account-modal"]');
        if (!btn) return;

        hiddenId.value = btn.dataset.baId;
        accountNumInput.value = btn.dataset.baAccountNum;

        var bankName = btn.dataset.baBankName;
        var bic = btn.dataset.baBic;
        var corrAccount = btn.dataset.baCorrAccount;

        hiddenBic.value = bic;
        hiddenBankName.value = bankName;
        hiddenCorrAccount.value = corrAccount;

        selectedName.textContent = bankName;
        selectedDetails.textContent = "БИК " + bic + " · К/с " + corrAccount;
        searchWrap.hidden = true;
        selectedWrap.hidden = false;
        manualWrap.hidden = true;
        isManualMode = false;

        updateAccountHint();
    });

    // ── Account number: digits only + counter ──

    function updateAccountHint() {
        if (!accountHint) return;
        var len = accountNumInput.value.length;
        accountHint.textContent = len === 0 ? "20 цифр" : len + " / " + ACCOUNT_LENGTH;
    }

    accountNumInput.addEventListener("input", function () {
        accountNumInput.value = accountNumInput.value.replace(/\D/g, "");
        accountNumInput.classList.remove("is-invalid");
        var err = accountNumInput.parentNode.querySelector(".modal-field-error");
        if (err) err.remove();
        updateAccountHint();
    });

    accountNumInput.addEventListener("paste", function (e) {
        e.preventDefault();
        var pasted = (e.clipboardData || window.clipboardData).getData("text");
        accountNumInput.value = pasted.replace(/\D/g, "").slice(0, ACCOUNT_LENGTH);
        accountNumInput.dispatchEvent(new Event("input"));
    });

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
                '<span class="suggest-item-title">' + ModalHelpers.escapeHtml(item.bank_name) + '</span>' +
                '<span class="suggest-item-sub">БИК ' + ModalHelpers.escapeHtml(item.bic) + '</span>';
            el.addEventListener("mousedown", function (e) {
                e.preventDefault();
                selectBank(item);
            });
            dropdown.appendChild(el);
        });
        activeIndex = -1;
        dropdown.classList.add("visible");
    }

    function selectBank(item) {
        hiddenBic.value = item.bic;
        hiddenBankName.value = item.bank_name;
        hiddenCorrAccount.value = item.corr_account;
        selectedName.textContent = item.bank_name;
        selectedDetails.textContent = "БИК " + item.bic + " · К/с " + item.corr_account;
        searchWrap.hidden = true;
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
        bic: "eba-bic",
        bank_name: "eba-bank-name",
        corr_account: "eba-corr-account",
        account_num: "eba-account-num"
    };
    var manualFieldMap = {
        bic: "eba-manual-bic",
        bank_name: "eba-manual-bank-name",
        corr_account: "eba-manual-corr-account"
    };

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        ModalHelpers.clearErrors(modal);
        if (isManualMode) syncManualToHidden();

        ModalHelpers.setSubmitting(submitBtn, true);

        var data = new FormData(form);
        var targetMap = isManualMode ? manualFieldMap : fieldMap;

        fetch(form.dataset.url, {
            method: "POST",
            body: data,
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
            .then(function (resp) {
                return resp.json().then(function (body) { return { ok: resp.ok, body: body }; });
            })
            .then(function (result) {
                if (result.ok || result.body.ok) {
                    window.location.reload();
                    return;
                }
                var mergedMap = {};
                for (var k in fieldMap) mergedMap[k] = targetMap[k] || fieldMap[k];
                ModalHelpers.applyFieldErrors(modal, mergedMap, result.body.errors || {}, errorsBox);
                ModalHelpers.setSubmitting(submitBtn, false);
            })
            .catch(function () {
                ModalHelpers.showGeneralError(errorsBox, "Ошибка сети. Попробуйте ещё раз.");
                ModalHelpers.setSubmitting(submitBtn, false);
            });
    });

    // Reset on modal close
    if (modal) {
        ModalHelpers.setupResetOnClose(modal, function () {
            updateAccountHint();
            hiddenBic.value = "";
            hiddenBankName.value = "";
            hiddenCorrAccount.value = "";
            isManualMode = false;
            searchWrap.hidden = false;
            selectedWrap.hidden = true;
            manualWrap.hidden = true;
            dropdown.classList.remove("visible");
            if (spin) spin.classList.remove("active");
        });
    }

    // ── Удаление банковского счёта ──

    var deleteModal = document.getElementById("delete-bank-account-modal");
    var deleteForm = document.getElementById("delete-bank-account-form");
    if (!deleteModal || !deleteForm) return;

    var deleteLabelSpan = document.getElementById("delete-ba-label");
    var deleteIdInput = document.getElementById("delete-ba-id");

    document.addEventListener("click", function (e) {
        var btn = e.target.closest('[data-modal-open="delete-bank-account-modal"]');
        if (!btn) return;
        deleteLabelSpan.textContent = btn.dataset.baLabel;
        deleteIdInput.value = btn.dataset.baId;
    });

    deleteForm.addEventListener("submit", function (e) {
        e.preventDefault();

        var deleteBtn = deleteForm.querySelector('button[type="submit"]');
        ModalHelpers.setSubmitting(deleteBtn, true);

        var data = new FormData(deleteForm);

        fetch(deleteForm.dataset.url, {
            method: "POST",
            body: data,
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
            .then(function (resp) {
                return resp.json().then(function (body) { return { ok: resp.ok, body: body }; });
            })
            .then(function (result) {
                if (result.ok || result.body.ok) {
                    window.location.reload();
                    return;
                }
                alert(result.body.error || "Ошибка при удалении");
                ModalHelpers.setSubmitting(deleteBtn, false);
            })
            .catch(function () {
                alert("Ошибка сети. Попробуйте ещё раз.");
                ModalHelpers.setSubmitting(deleteBtn, false);
            });
    });
});
