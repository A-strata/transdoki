(function () {
    "use strict";

    /* ── Базовые цены (месячные) ── */
    var BASE = {
        start: 790, biz: 1990, corp: 3990,
        carrier: 990, fuel: 490, fin: 1490, contr: 490
    };

    var billing = "month";
    var seg = "carrier";

    /* ── Конфигурация сегментов ── */
    var SEG = {
        carrier: {
            title: "Модули для перевозчика",
            mods: { carrier: "rec", fuel: "vis", fin: "dim", contr: "vis" },
            badges: {
                carrier: ["rec", "Рекомендуем"],
                fuel: ["neutral", "К модулю \u00abПеревозчик\u00bb"],
                fin: ["neutral", "Для экспедиторов"],
                contr: ["neutral", "Для всех"]
            },
            note: function () {
                return "Небольшому перевозчику (до 5 машин) достаточно Freemium + модуль \u00abПеревозчик\u00bb \u2014 итого <strong>" +
                    fmt(price("carrier")) + "/мес</strong>. Топливные карты \u2014 по необходимости.";
            }
        },
        exp: {
            title: "Модули для экспедитора",
            mods: { carrier: "dim", fuel: "dim", fin: "rec", contr: "rec" },
            badges: {
                carrier: ["neutral", "Для перевозчиков"],
                fuel: ["neutral", "Для перевозчиков"],
                fin: ["rec", "Рекомендуем"],
                contr: ["rec", "Рекомендуем"]
            },
            note: function () {
                return "Рекомендуем: тариф \u00abБизнес\u00bb + модули \u00abФинансы\u00bb и \u00abДоговоры\u00bb \u2014 итого <strong>" +
                    fmt(price("biz") + price("fin") + price("contr")) + "/мес</strong>.";
            }
        },
        customer: {
            title: "Модули для заказчика",
            mods: { carrier: "dim", fuel: "dim", fin: "rec", contr: "vis" },
            badges: {
                carrier: ["neutral", "Для перевозчиков"],
                fuel: ["neutral", "Для перевозчиков"],
                fin: ["rec", "Рекомендуем"],
                contr: ["neutral", "Для всех"]
            },
            note: function () {
                return "Рекомендуем: тариф \u00abБизнес\u00bb + модуль \u00abФинансы\u00bb \u2014 итого <strong>" +
                    fmt(price("biz") + price("fin")) + "/мес</strong>. Договоры \u2014 по необходимости.";
            }
        }
    };

    function price(key) {
        return billing === "year" ? Math.round(BASE[key] * 0.8) : BASE[key];
    }

    function fmt(n) {
        return n.toLocaleString("ru-RU") + "\u202f\u20bd";
    }

    /* ── Рендеринг ── */
    function render() {
        var disc = billing === "year";
        var cfg = SEG[seg];

        /* Toggle */
        var toggle = document.getElementById("billing-toggle");
        if (toggle) {
            toggle.className = "billing-toggle" + (disc ? " is-on" : "");
        }
        var lblM = document.getElementById("lbl-month");
        var lblY = document.getElementById("lbl-year");
        if (lblM) lblM.className = "billing-label" + (billing === "month" ? " is-active" : "");
        if (lblY) lblY.className = "billing-label" + (billing === "year" ? " is-active" : "");

        /* Цены тарифов */
        ["start", "biz", "corp"].forEach(function (k) {
            var shown = price(k);
            var orig = BASE[k];

            var priceEl = document.querySelector("[data-price='" + k + "']");
            if (priceEl) priceEl.textContent = fmt(shown);

            var origEl = document.querySelector("[data-orig='" + k + "']");
            if (origEl) {
                origEl.style.display = disc ? "inline" : "none";
                origEl.textContent = fmt(orig);
            }

            var periodEl = document.querySelector("[data-period='" + k + "']");
            if (periodEl) {
                periodEl.textContent = disc ? "в месяц \u00b7 при оплате за год" : "в месяц";
            }

            var afterEl = document.querySelector("[data-after='" + k + "']");
            if (afterEl) afterEl.textContent = fmt(shown) + "/мес";
        });

        /* Цены модулей */
        ["carrier", "fuel", "fin", "contr"].forEach(function (k) {
            var priceEl = document.querySelector("[data-mprice='" + k + "']");
            if (priceEl) priceEl.textContent = fmt(price(k)) + "/мес";

            var origEl = document.querySelector("[data-morig='" + k + "']");
            if (origEl) {
                origEl.style.display = disc ? "inline" : "none";
                origEl.textContent = fmt(BASE[k]);
            }
        });

        /* Заголовок модулей + подсказка */
        var modTitle = document.getElementById("modules-title");
        if (modTitle) modTitle.textContent = cfg.title;

        var segNote = document.getElementById("seg-note");
        if (segNote) segNote.innerHTML = cfg.note();

        /* Состояния карточек модулей */
        var modKeys = ["carrier", "fuel", "fin", "contr"];
        modKeys.forEach(function (k) {
            var card = document.querySelector("[data-module='" + k + "']");
            if (!card) return;

            var st = cfg.mods[k];
            card.className = "module-card" +
                (st === "rec" ? " is-recommended" : st === "vis" ? " is-visible" : "");

            var badge = document.querySelector("[data-mbadge='" + k + "']");
            if (badge) {
                var badgeCfg = cfg.badges[k];
                badge.className = "module-badge is-" + badgeCfg[0];
                badge.textContent = badgeCfg[1];
            }
        });

        /* Табы сегментов */
        document.querySelectorAll(".seg-tab").forEach(function (el) {
            el.className = "seg-tab" + (el.dataset.seg === seg ? " is-active" : "");
        });
    }

    /* ── Обработчики ── */
    function toggleBilling() {
        billing = billing === "month" ? "year" : "month";
        render();
    }

    function setBilling(value) {
        billing = value;
        render();
    }

    function setSeg(value) {
        seg = value;
        render();
    }

    /* Billing toggle */
    var toggleBtn = document.getElementById("billing-toggle");
    if (toggleBtn) {
        toggleBtn.addEventListener("click", toggleBilling);
    }

    var lblMonth = document.getElementById("lbl-month");
    if (lblMonth) {
        lblMonth.addEventListener("click", function () { setBilling("month"); });
    }

    var lblYear = document.getElementById("lbl-year");
    if (lblYear) {
        lblYear.addEventListener("click", function () { setBilling("year"); });
    }

    /* Segment tabs */
    document.querySelectorAll(".seg-tab").forEach(function (tab) {
        tab.addEventListener("click", function () {
            setSeg(tab.dataset.seg);
        });
    });

    /* Year banner */
    var yearBtn = document.getElementById("year-banner-btn");
    if (yearBtn) {
        yearBtn.addEventListener("click", function () {
            setBilling("year");
            window.scrollTo({ top: 0, behavior: "smooth" });
        });
    }

    /* FAQ accordion */
    document.querySelectorAll(".faq-item").forEach(function (item) {
        var btn = item.querySelector(".faq-q");
        if (!btn) return;

        btn.addEventListener("click", function () {
            var isOpen = item.classList.contains("is-open");

            document.querySelectorAll(".faq-item").forEach(function (i) {
                i.classList.remove("is-open");
                var body = i.querySelector(".faq-body");
                if (body) body.style.maxHeight = "0";
            });

            if (!isOpen) {
                item.classList.add("is-open");
                var body = item.querySelector(".faq-body");
                var inner = item.querySelector(".faq-inner");
                if (body && inner) {
                    body.style.maxHeight = inner.offsetHeight + 32 + "px";
                }
            }
        });
    });

    /* Первый рендер */
    render();
})();
