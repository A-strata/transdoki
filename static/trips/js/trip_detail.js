document.addEventListener('DOMContentLoaded', function () {

    var ICON_SVG =
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>' +
        '<path d="M14 2v4a2 2 0 0 0 2 2h4"/>' +
        '<path d="M10 13h4"/>' +
        '<path d="M10 17h4"/>' +
        '</svg>';

    var ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx'];
    var MAX_FILE_SIZE = 20 * 1024 * 1024; // 20 MB

    /* ── DOM-элементы ── */
    var fileInput = document.getElementById('file-input');
    var uploadForm = document.querySelector('.file-upload-form');
    var uploadTrigger = document.querySelector('.upload-trigger');
    var fileListEl = document.querySelector('.file-list-preview');
    var uploadActions = document.querySelector('.upload-actions');
    var submitBtn = document.querySelector('.upload-submit');
    var cancelBtn = document.querySelector('.upload-cancel');
    var noticeEl = document.querySelector('.upload-notice');
    var limitHintEl = document.querySelector('.upload-limit-hint');
    var counterEl = document.querySelector('.upload-counter');
    var attachmentsList = document.querySelector('.attachments-list');

    var maxFiles = uploadForm ? parseInt(uploadForm.dataset.maxFiles, 10) || 10 : 10;
    var pendingFiles = [];

    /* ── Клик по триггеру → открыть file picker ── */
    if (uploadTrigger && fileInput) {
        uploadTrigger.addEventListener('click', function () {
            fileInput.click();
        });
    }

    if (fileInput && uploadForm && fileListEl) {

        /* ── Выбор файлов ── */
        fileInput.addEventListener('change', function () {
            clearNotice();
            var warnings = [];

            for (var i = 0; i < fileInput.files.length; i++) {
                var file = fileInput.files[i];
                var result = validateAndAdd(file);
                if (result) warnings.push(result);
            }

            fileInput.value = '';
            renderPendingFiles();
            updateTriggerState();

            if (warnings.length) {
                showNotice(warnings.join('\n'), 'warning');
            }
        });

        /* ── Удаление отдельного файла ── */
        fileListEl.addEventListener('click', function (e) {
            var removeBtn = e.target.closest('.file-list-remove');
            if (!removeBtn) return;
            var index = parseInt(removeBtn.dataset.index, 10);
            pendingFiles.splice(index, 1);
            clearNotice();
            renderPendingFiles();
            updateTriggerState();
        });

        /* ── Отмена ── */
        if (cancelBtn) {
            cancelBtn.addEventListener('click', function () {
                resetUploadForm();
            });
        }

        /* ── Отправка ── */
        uploadForm.addEventListener('submit', function (e) {
            e.preventDefault();
            if (!pendingFiles.length) return;
            clearNotice();

            var formData = new FormData();
            var csrfInput = uploadForm.querySelector('[name="csrfmiddlewaretoken"]');
            if (csrfInput) formData.append('csrfmiddlewaretoken', csrfInput.value);
            for (var i = 0; i < pendingFiles.length; i++) {
                formData.append('files', pendingFiles[i]);
            }

            var csrfToken = csrfInput ? csrfInput.value : '';
            var fileCount = pendingFiles.length;

            // Состояние загрузки
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Загрузка... (' + fileCount + ')';
            }
            if (cancelBtn) cancelBtn.disabled = true;
            fileListEl.classList.add('is-loading');

            fetch(uploadForm.action, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: formData,
            }).then(function (resp) {
                return resp.json().then(function (data) {
                    return { ok: resp.ok, data: data };
                });
            }).then(function (result) {
                if (!result.ok || !result.data.ok) {
                    var msg = (result.data && result.data.error) || 'Ошибка загрузки файлов.';
                    showNotice(msg, 'error');
                    return;
                }

                // Убрать пустое состояние
                if (attachmentsList) {
                    var emptyHint = attachmentsList.querySelector('.empty-hint');
                    if (emptyHint) emptyHint.remove();
                }

                // Добавить загруженные файлы в DOM
                var attachments = result.data.attachments || [];
                attachments.forEach(function (att) {
                    if (attachmentsList) {
                        attachmentsList.appendChild(buildAttachmentItem(att));
                    }
                });

                resetUploadForm();
            }).catch(function () {
                showNotice('Не удалось загрузить файлы. Попробуйте обновить страницу.', 'error');
            }).finally(function () {
                fileListEl.classList.remove('is-loading');
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Отправить';
                }
                if (cancelBtn) cancelBtn.disabled = false;
            });
        });
    }

    /* ── Валидация и добавление файла ── */
    function validateAndAdd(file) {
        var ext = file.name.split('.').pop().toLowerCase();
        if (ALLOWED_EXTENSIONS.indexOf(ext) === -1) {
            return '«' + file.name + '» — недопустимый формат. Разрешены: ' + ALLOWED_EXTENSIONS.join(', ');
        }
        if (file.size > MAX_FILE_SIZE) {
            return '«' + file.name + '» — размер ' + formatSize(file.size) + ' превышает лимит 20 МБ';
        }
        var totalCount = getExistingCount() + pendingFiles.length;
        if (totalCount >= maxFiles) {
            return '«' + file.name + '» — достигнут лимит ' + maxFiles + ' файлов на рейс';
        }
        if (isDuplicate(file)) {
            return '«' + file.name + '» уже добавлен';
        }
        pendingFiles.push(file);
        return null;
    }

    /* ── Дедупликация ── */
    function isDuplicate(file) {
        // Среди pending-файлов
        for (var i = 0; i < pendingFiles.length; i++) {
            var existing = pendingFiles[i];
            if (existing.name === file.name && existing.size === file.size) {
                if (file.lastModified === 0 || existing.lastModified === 0) return true;
                if (existing.lastModified === file.lastModified) return true;
            }
        }
        // Среди уже загруженных на сервер
        if (attachmentsList) {
            var names = attachmentsList.querySelectorAll('.attachment-name');
            for (var j = 0; j < names.length; j++) {
                if (names[j].textContent.trim() === file.name) return true;
            }
        }
        return false;
    }

    /* ── Счётчик существующих файлов в DOM ── */
    function getExistingCount() {
        if (!attachmentsList) return 0;
        return attachmentsList.querySelectorAll('.attachment-item').length;
    }

    /* ── Состояние кнопки «+ Загрузить файлы» ── */
    function updateTriggerState() {
        if (!uploadTrigger || !limitHintEl) return;
        var total = getExistingCount() + pendingFiles.length;
        if (total >= maxFiles) {
            uploadTrigger.disabled = true;
            limitHintEl.textContent = 'Достигнут лимит — ' + maxFiles + ' файлов';
            limitHintEl.hidden = false;
        } else {
            uploadTrigger.disabled = false;
            limitHintEl.hidden = true;
        }
    }

    /* ── Рендер списка pending-файлов ── */
    function renderPendingFiles() {
        fileListEl.innerHTML = '';

        if (!pendingFiles.length) {
            fileListEl.hidden = true;
            if (uploadActions) uploadActions.hidden = true;
            if (counterEl) counterEl.hidden = true;
            if (submitBtn) submitBtn.textContent = 'Отправить';
            return;
        }

        for (var i = 0; i < pendingFiles.length; i++) {
            var file = pendingFiles[i];
            var item = document.createElement('div');
            item.className = 'file-list-item';
            item.innerHTML =
                '<span class="file-list-name">' + escapeHtml(file.name) + '</span>' +
                '<span class="file-list-size">' + formatSize(file.size) + '</span>' +
                '<button type="button" class="file-list-remove" data-index="' + i + '"' +
                    ' title="Убрать ' + escapeHtml(file.name) + '"' +
                    ' aria-label="Убрать ' + escapeHtml(file.name) + '">' +
                    '<svg width="16" height="16" viewBox="0 0 16 16" fill="none">' +
                    '<path d="M2 4h12" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>' +
                    '<path d="M13 4v9.5a1.5 1.5 0 0 1-1.5 1.5h-7A1.5 1.5 0 0 1 3 13.5V4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>' +
                    '<path d="M5.5 4V2.5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1V4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>' +
                    '</svg></button>';
            fileListEl.appendChild(item);
        }

        fileListEl.hidden = false;
        if (uploadActions) uploadActions.hidden = false;
        if (submitBtn) {
            submitBtn.textContent = 'Отправить (' + pendingFiles.length + ')';
        }

        // Счётчик слотов
        if (counterEl) {
            var remaining = maxFiles - getExistingCount() - pendingFiles.length;
            counterEl.textContent = pluralFiles(pendingFiles.length) + ' · осталось ' + remaining + ' ' + pluralSlots(remaining);
            counterEl.hidden = false;
        }
    }

    /* ── Inline-уведомления ── */
    var WARN_ICON =
        '<svg class="upload-notice-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>' +
        '<path d="M12 9v4"/><path d="M12 17h.01"/>' +
        '</svg>';

    function showNotice(text, type) {
        if (!noticeEl) return;
        var lines = text.split('\n');
        var html = WARN_ICON + '<div class="upload-notice-body">';
        for (var i = 0; i < lines.length; i++) {
            html += '<p>' + escapeHtml(lines[i]) + '</p>';
        }
        html += '</div>';
        noticeEl.innerHTML = html;
        noticeEl.className = 'upload-notice is-' + type;
        noticeEl.hidden = false;
    }

    function clearNotice() {
        if (!noticeEl) return;
        noticeEl.hidden = true;
        noticeEl.innerHTML = '';
        noticeEl.className = 'upload-notice';
    }

    /* ── Сброс формы ── */
    function resetUploadForm() {
        pendingFiles = [];
        if (fileInput) fileInput.value = '';
        if (fileListEl) {
            fileListEl.innerHTML = '';
            fileListEl.hidden = true;
        }
        if (uploadActions) uploadActions.hidden = true;
        if (counterEl) counterEl.hidden = true;
        if (submitBtn) submitBtn.textContent = 'Отправить';
        clearNotice();
        updateTriggerState();
    }

    /* ── Построение DOM-элемента вложения ── */
    function buildAttachmentItem(att) {
        var item = document.createElement('div');
        item.className = 'attachment-item';

        item.innerHTML =
            '<div class="attachment-main">' +
                '<span class="attachment-icon" aria-hidden="true">' + ICON_SVG + '</span>' +
                '<div class="attachment-text">' +
                    '<p class="attachment-name">' + escapeHtml(att.original_name) + '</p>' +
                    '<p class="kv-label">' + escapeHtml(att.created_at) + '</p>' +
                '</div>' +
            '</div>' +
            '<div class="attachment-actions">' +
                '<a href="' + att.download_url + '" class="tms-btn tms-btn-secondary tms-btn-sm">Скачать</a>' +
                '<button type="button" class="attachment-delete"' +
                    ' data-modal-open="delete-attachment-modal"' +
                    ' data-delete-url="' + att.delete_url + '"' +
                    ' data-delete-name="' + escapeHtml(att.original_name) + '"' +
                    ' title="Удалить" aria-label="Удалить ' + escapeHtml(att.original_name) + '">' +
                    '<svg width="16" height="16" viewBox="0 0 16 16" fill="none">' +
                    '<path d="M2 4h12" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>' +
                    '<path d="M13 4v9.5a1.5 1.5 0 0 1-1.5 1.5h-7A1.5 1.5 0 0 1 3 13.5V4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>' +
                    '<path d="M5.5 4V2.5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1V4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>' +
                    '</svg></button>' +
            '</div>';

        return item;
    }

    /* ── Удаление вложения через модалку (fetch + DOM removal) ── */
    var deleteForm = document.getElementById('delete-attachment-form');
    var deleteModal = document.getElementById('delete-attachment-modal');
    var activeTrigger = null;

    if (deleteForm && deleteModal) {
        deleteForm.addEventListener('submit', function (e) {
            e.preventDefault();

            var url = deleteForm.action;
            if (!url) return;

            var csrfInput = deleteForm.querySelector('[name="csrfmiddlewaretoken"]');
            var csrfToken = csrfInput ? csrfInput.value : '';

            var btn = deleteForm.querySelector('[type="submit"]');
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
            }).then(function (resp) {
                if (!resp.ok) throw new Error('Server error');

                if (activeTrigger) {
                    var item = activeTrigger.closest('.attachment-item');
                    if (item) item.remove();
                }

                if (attachmentsList && !attachmentsList.querySelector('.attachment-item')) {
                    attachmentsList.innerHTML = '<p class="empty-hint">Файлы пока не прикреплены.</p>';
                }

                deleteModal.hidden = true;
                updateTriggerState();
            }).catch(function () {
                deleteModal.hidden = true;
                showNotice('Не удалось удалить файл. Попробуйте обновить страницу.', 'error');
            }).finally(function () {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = 'Удалить';
                }
                activeTrigger = null;
            });
        });

        document.addEventListener('click', function (e) {
            var opener = e.target.closest('[data-modal-open="delete-attachment-modal"]');
            if (opener) {
                activeTrigger = opener;
            }
        });
    }

    /* ── Утилиты ── */
    function formatSize(bytes) {
        if (bytes < 1024) return bytes + ' Б';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' КБ';
        return (bytes / (1024 * 1024)).toFixed(1) + ' МБ';
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function pluralFiles(n) {
        var mod = n % 10;
        var mod100 = n % 100;
        if (mod === 1 && mod100 !== 11) return n + ' файл';
        if (mod >= 2 && mod <= 4 && (mod100 < 12 || mod100 > 14)) return n + ' файла';
        return n + ' файлов';
    }

    function pluralSlots(n) {
        var mod = n % 10;
        var mod100 = n % 100;
        if (mod === 1 && mod100 !== 11) return 'слот';
        if (mod >= 2 && mod <= 4 && (mod100 < 12 || mod100 > 14)) return 'слота';
        return 'слотов';
    }

    /* ── Начальное состояние ── */
    updateTriggerState();
});
