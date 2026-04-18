(function () {
    "use strict";

    var QUERY = "Москва, Складской";
    var RESULT = "Москва, Складской пр-д, д. 3с1";
    var LOOP_PAUSE = 3200;
    var timers = [];
    var autoLoop = false;
    var isPlaying = false;

    function clr() {
        timers.forEach(function (t) { clearTimeout(t); });
        timers = [];
    }

    function schedule(fn, ms) {
        timers.push(setTimeout(fn, ms));
    }

    function run() {
        isPlaying = true;
        clr();

        var textEl    = document.getElementById("cf-addr-text-from");
        var curEl     = document.getElementById("cf-addr-cur-from");
        var inputFrom = document.getElementById("cf-addr-input-from");
        var dd        = document.getElementById("cf-addr-dd");
        var confirmed = document.getElementById("cf-addr-confirmed");
        var inputTo   = document.getElementById("cf-addr-input-to");
        var replay    = document.getElementById("cf-addr-replay");

        if (!textEl) return;

        textEl.textContent  = "";
        curEl.className     = "cf-addr-cursor cf-addr-cursor--blink";
        inputFrom.className = "cf-addr-input cf-addr-input--focused";
        dd.className        = "cf-addr-dropdown";
        confirmed.hidden    = true;
        inputTo.className   = "cf-addr-input cf-addr-input--empty";
        inputTo.textContent = "Введите адрес...";
        replay.hidden       = true;

        var i = 0;
        function type() {
            if (i < QUERY.length) {
                textEl.textContent = QUERY.slice(0, i + 1);
                i++;
                schedule(type, i < 6 ? 100 : i < 12 ? 75 : 55);
            } else {
                schedule(showDropdown, 200);
                schedule(selectItem, 1500);
            }
        }
        schedule(type, 600);

        function showDropdown() {
            dd.className = "cf-addr-dropdown cf-addr-dropdown--visible";
        }

        function selectItem() {
            dd.className = "cf-addr-dropdown";
            schedule(function () {
                textEl.textContent  = RESULT;
                curEl.className     = "cf-addr-cursor";
                inputFrom.className = "cf-addr-input cf-addr-input--done";
                confirmed.hidden    = false;
            }, 250);
            schedule(function () {
                inputTo.className   = "cf-addr-input cf-addr-input--focused";
                inputTo.textContent = "";
            }, 700);
            schedule(function () {
                replay.hidden = false;
                isPlaying = false;
                if (autoLoop) {
                    schedule(run, LOOP_PAUSE);
                }
            }, 1200);
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        var btn = document.getElementById("cf-addr-replay");
        if (!btn) return;
        btn.addEventListener("click", function () {
            autoLoop = true;
            run();
        });

        var target = document.querySelector(".features-cf-demo--address");
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
