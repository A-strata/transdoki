(function () {
    "use strict";

    var anchors = document.querySelectorAll(".features-anchor");
    var sections = document.querySelectorAll(".features-section");
    if (!anchors.length || !sections.length) return;

    var scrollContainer = document.querySelector("main");
    if (!scrollContainer) return;

    function updateActive() {
        var scrollTop = scrollContainer.scrollTop;
        var offset = 140;
        var currentId = "";

        for (var i = 0; i < sections.length; i++) {
            var section = sections[i];
            if (section.offsetTop - offset <= scrollTop) {
                currentId = section.id;
            }
        }

        anchors.forEach(function (a) {
            var isActive = a.getAttribute("href") === "#" + currentId;
            a.classList.toggle("is-active", isActive);
        });
    }

    scrollContainer.addEventListener("scroll", updateActive, { passive: true });

    anchors.forEach(function (a) {
        a.addEventListener("click", function (e) {
            e.preventDefault();
            var targetId = a.getAttribute("href").slice(1);
            var target = document.getElementById(targetId);
            if (!target) return;

            var navHeight = 130;
            var top = target.offsetTop - navHeight;
            scrollContainer.scrollTo({ top: top, behavior: "smooth" });
        });
    });

    updateActive();
})();
