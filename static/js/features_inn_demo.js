(function () {
    "use strict";

    var INN = "7732045123";
    var DATA = {
        name:   "ООО «Ромашка Логистик»",
        kpp:    "773201001",
        ogrn:   "1187746312049",
        addr:   "г. Москва, ул. Ленинградская, д. 14, офис 201",
        ceo:    "Иванов А.В.",
        status: "Действующая"
    };
    var FIELDS = [
        { id: "cf-inn-f-name",   key: "name",   success: false, delay: 0   },
        { id: "cf-inn-f-kpp",    key: "kpp",    success: false, delay: 120 },
        { id: "cf-inn-f-ogrn",   key: "ogrn",   success: false, delay: 240 },
        { id: "cf-inn-f-addr",   key: "addr",   success: false, delay: 360 },
        { id: "cf-inn-f-ceo",    key: "ceo",    success: false, delay: 480 },
        { id: "cf-inn-f-status", key: "status", success: true,  delay: 600 }
    ];

    var LOOP_PAUSE = 3200;
    var timers = [];
    var autoLoop = false;
    var isPlaying = false;

    function clr() {
        timers.forEach(function (t) { clearTimeout(t); });
        timers = [];
    }

    function s(fn, ms) {
        timers.push(setTimeout(fn, ms));
    }

    function getEl(id) {
        return document.getElementById(id);
    }

    function iconSearch() {
        return '<svg width="12" height="12" viewBox="0 0 24 24" fill="none"' +
            ' stroke="currentColor" stroke-width="2" stroke-linecap="round"' +
            ' stroke-linejoin="round" aria-hidden="true">' +
            '<circle cx="11" cy="11" r="8"/>' +
            '<line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>';
    }

    function iconSpinner() {
        return '<svg width="12" height="12" viewBox="0 0 24 24" fill="none"' +
            ' stroke="currentColor" stroke-width="2" stroke-linecap="round"' +
            ' stroke-linejoin="round" aria-hidden="true">' +
            '<path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>';
    }

    function iconCheck() {
        return '<svg width="12" height="12" viewBox="0 0 24 24" fill="none"' +
            ' stroke="currentColor" stroke-width="2.5" stroke-linecap="round"' +
            ' stroke-linejoin="round" aria-hidden="true">' +
            '<polyline points="20 6 9 17 4 12"/></svg>';
    }

    function reset() {
        var txtEl  = getEl("cf-inn-text");
        var curEl  = getEl("cf-inn-cur");
        var inp    = getEl("cf-inn-input");
        var btn    = getEl("cf-inn-btn");
        var replay = getEl("cf-inn-replay");

        if (!txtEl) return;

        txtEl.textContent = "";
        curEl.className   = "cf-inn-cursor cf-inn-cursor--blink";
        inp.className     = "cf-inn-input cf-inn-input--focused";
        btn.disabled      = true;
        btn.className     = "cf-inn-btn";
        btn.innerHTML     = iconSearch() + " Заполнить по ИНН";
        replay.hidden     = true;

        FIELDS.forEach(function (f) {
            var el = getEl(f.id);
            if (!el) return;
            el.className   = "cf-inn-result-value";
            el.textContent = "—";
        });
    }

    function run() {
        clr();
        reset();
        isPlaying = true;

        var txtEl = getEl("cf-inn-text");
        var curEl = getEl("cf-inn-cur");
        var inp   = getEl("cf-inn-input");
        var btn   = getEl("cf-inn-btn");

        if (!txtEl) return;

        var i = 0;
        function type() {
            if (i < INN.length) {
                txtEl.textContent = INN.slice(0, i + 1);
                i++;
                s(type, i < 4 ? 110 : i < 8 ? 85 : 65);
            } else {
                s(function () {
                    curEl.className = "cf-inn-cursor";
                    inp.className   = "cf-inn-input";
                    btn.disabled    = false;
                }, 300);
                s(clickBtn, 900);
            }
        }
        s(type, 500);

        function clickBtn() {
            btn.className = "cf-inn-btn cf-inn-btn--loading";
            btn.innerHTML = iconSpinner() + " Запрос в ФНС...";
            btn.disabled  = true;
            s(fillFields, 900);
        }

        function fillFields() {
            btn.className = "cf-inn-btn cf-inn-btn--done";
            btn.innerHTML = iconCheck() + " Заполнено";
            btn.disabled  = true;

            FIELDS.forEach(function (f) {
                s(function () {
                    var el = getEl(f.id);
                    if (!el) return;
                    el.textContent = DATA[f.key];
                    el.className   = "cf-inn-result-value" +
                        (f.success ? " cf-inn-result-value--success"
                                   : " cf-inn-result-value--filled");
                }, f.delay);
            });

            s(function () {
                var replay = getEl("cf-inn-replay");
                if (replay) replay.hidden = false;
                isPlaying = false;
                if (autoLoop) {
                    s(run, LOOP_PAUSE);
                }
            }, 800);
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        var btn = getEl("cf-inn-replay");
        if (!btn) return;
        btn.addEventListener("click", function () {
            autoLoop = true;
            run();
        });

        var target = document.querySelector(".features-cf-demo--inn");
        if (!target || typeof IntersectionObserver === "undefined") {
            autoLoop = true;
            run();
            return;
        }

        // Скролл в проекте — внутри <main>, не window (ui-guide раздел 8).
        // threshold: 1.0 = запуск только когда блок-демо полностью виден.
        // На случай, если демо крупнее viewport — ещё отслеживаем ratio близко к 1.
        // Observer оставляем подключённым: при уходе блока — останавливаем цикл,
        // при возврате — запускаем снова.
        var root = document.querySelector("main") || null;
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                var rootHeight = (root ? root.clientHeight : window.innerHeight);
                var fitsInViewport = entry.boundingClientRect.height <= rootHeight;
                var fullyVisible = fitsInViewport
                    ? entry.intersectionRatio >= 1
                    : entry.intersectionRect.height >= rootHeight - 4;

                if (fullyVisible) {
                    if (!autoLoop) {
                        autoLoop = true;
                        if (!isPlaying) run();
                    }
                } else {
                    autoLoop = false;
                    clr();
                    isPlaying = false;
                }
            });
        }, { root: root, threshold: [0, 0.5, 0.9, 1.0] });
        observer.observe(target);
    });
}());
