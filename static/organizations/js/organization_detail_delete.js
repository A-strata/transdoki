/**
 * Удаление ТС и водителей на странице карточки контрагента.
 * Fetch + DOM update — без перезагрузки страницы.
 */
(function () {
    'use strict';

    function setupDeleteModal(modalId, rowSelector, badgeUpdateFn) {
        var modal = document.getElementById(modalId);
        if (!modal) return;

        var form = modal.querySelector('form');
        if (!form) return;

        form._targetRow = null;

        document.addEventListener('click', function (e) {
            var opener = e.target.closest('[data-modal-open="' + modalId + '"]');
            if (opener) form._targetRow = opener.closest(rowSelector);
        });

        form.addEventListener('submit', function (e) {
            e.preventDefault();

            var url = form.action;
            if (!url) return;

            var targetRow = form._targetRow;
            var csrfInput = form.querySelector('[name="csrfmiddlewaretoken"]');
            var csrfToken = csrfInput ? csrfInput.value : '';

            var btn = form.querySelector('[type="submit"]');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Удаление...';
            }

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
            })
                .then(function (resp) {
                    if (resp.status === 409) {
                        return resp.json().then(function (data) {
                            throw new Error(data.error || 'Невозможно удалить.');
                        });
                    }
                    if (!resp.ok) throw new Error('Ошибка сервера');
                    return resp.json();
                })
                .then(function () {
                    if (targetRow) {
                        var tbody = targetRow.closest('tbody');
                        targetRow.remove();
                        if (badgeUpdateFn) badgeUpdateFn(tbody);
                    }
                    modal.hidden = true;
                })
                .catch(function (err) {
                    modal.hidden = true;
                    showFlash(err.message || 'Не удалось удалить. Попробуйте обновить страницу.', 'error');
                })
                .finally(function () {
                    if (btn) {
                        btn.disabled = false;
                        btn.textContent = 'Удалить';
                    }
                    form._targetRow = null;
                });
        });
    }

    function showFlash(message, level) {
        var wrap = document.querySelector('.flash-wrap');
        if (!wrap) {
            wrap = document.createElement('div');
            wrap.className = 'flash-wrap';
            var main = document.querySelector('main');
            if (main) main.prepend(wrap);
        }
        var flash = document.createElement('div');
        flash.className = 'flash flash-' + (level || 'error');
        flash.setAttribute('data-autohide', level === 'error' ? '0' : '1');
        flash.textContent = message;
        var closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'flash-close';
        closeBtn.setAttribute('aria-label', 'Закрыть');
        closeBtn.textContent = '\u00d7';
        closeBtn.addEventListener('click', function () { flash.remove(); });
        flash.appendChild(closeBtn);
        wrap.appendChild(flash);
    }

    function updateSectionBadge(tbody) {
        if (!tbody) return;
        var section = tbody.closest('.collapsible-section');
        if (!section) return;

        var remaining = tbody.querySelectorAll('tr').length;
        var badge = section.querySelector('.collapsible-badge');
        var hint = section.querySelector('.collapsible-hint');

        if (remaining > 0) {
            if (badge) badge.textContent = remaining;
            if (hint) hint.remove();
        } else {
            if (badge) badge.remove();
            var titleWrap = section.querySelector('.collapsible-title-wrap');
            if (titleWrap && !titleWrap.querySelector('.collapsible-hint')) {
                var hintEl = document.createElement('span');
                hintEl.className = 'collapsible-hint';
                hintEl.textContent = 'пусто';
                titleWrap.appendChild(hintEl);
            }
            var table = section.querySelector('table');
            if (table) {
                var empty = document.createElement('p');
                empty.className = 'collapsible-empty';
                empty.textContent = table.dataset.emptyText || 'Нет данных';
                table.replaceWith(empty);
            }
            section.classList.remove('is-open');
        }
    }

    setupDeleteModal('delete-vehicle-modal', 'tr', updateSectionBadge);
    setupDeleteModal('delete-person-modal', 'tr', updateSectionBadge);
})();
