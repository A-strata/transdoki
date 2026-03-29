/**
 * Коллапсируемые секции карточки организации.
 *
 * Разметка:
 *   <div class="collapsible-section [is-open]" data-collapsible>
 *       <div class="collapsible-header" data-collapsible-toggle>
 *           ...
 *           <button data-collapsible-action ...>+ Добавить</button>
 *       </div>
 *       <div class="collapsible-body">...</div>
 *   </div>
 *
 * Клик по header — toggle. Клик по кнопке с data-collapsible-action —
 * не вызывает toggle (проверка target вместо stopPropagation,
 * чтобы не блокировать делегированные обработчики в base.js).
 */
document.querySelectorAll("[data-collapsible]").forEach(function (section) {
    var header = section.querySelector("[data-collapsible-toggle]");
    if (!header) return;

    header.addEventListener("click", function (e) {
        if (e.target.closest("[data-collapsible-action]")) return;
        section.classList.toggle("is-open");
    });
});
