(function () {
    function init() {
        const form = document.querySelector('[data-trip-filters]');
        if (!form) return;

        const pageSizeSelect = form.querySelector('[data-filter="page_size"]');
        const resetBtn = form.querySelector('[data-filter="reset"]');
        const submitBtn = form.querySelector('[data-submit-filters]');
        const currentPageInput = form.querySelector('input[name="page"]');
        const currentPageSizeInput = form.querySelector('input[name="current_page_size"]');
        const dateFromInput = form.querySelector('[data-filter="date_from"]');
        const dateToInput = form.querySelector('[data-filter="date_to"]');
        const quickDateButtons = form.querySelectorAll('[data-quick-date]');

        function resetPageToFirst() {
            if (currentPageInput) {
                currentPageInput.value = '1';
            }
        }

        function formatDate(date) {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        }

        function getShiftedDate(days) {
            const date = new Date();
            date.setHours(12, 0, 0, 0);
            date.setDate(date.getDate() + days);
            return formatDate(date);
        }

        function updateQuickDateState() {
            if (!dateFromInput || !dateToInput || !quickDateButtons.length) {
                return;
            }

            const fromValue = dateFromInput.value;
            const toValue = dateToInput.value;

            const yesterday = getShiftedDate(-1);
            const today = getShiftedDate(0);
            const tomorrow = getShiftedDate(1);

            let activeType = '';

            if (fromValue && toValue && fromValue === toValue) {
                if (fromValue === yesterday) {
                    activeType = 'yesterday';
                } else if (fromValue === today) {
                    activeType = 'today';
                } else if (fromValue === tomorrow) {
                    activeType = 'tomorrow';
                }
            }

            quickDateButtons.forEach((button) => {
                button.classList.toggle(
                    'is-active',
                    button.getAttribute('data-quick-date') === activeType
                );
            });
        }

        if (submitBtn) {
            submitBtn.addEventListener('click', function () {
                resetPageToFirst();
            });
        }

        form.addEventListener('submit', function (event) {
            const submitter = event.submitter;

            if (submitter && submitter === submitBtn) {
                resetPageToFirst();
            }
        });

        quickDateButtons.forEach((button) => {
            button.addEventListener('click', function () {
                const type = button.getAttribute('data-quick-date');
                let value = '';

                if (type === 'yesterday') {
                    value = getShiftedDate(-1);
                } else if (type === 'today') {
                    value = getShiftedDate(0);
                } else if (type === 'tomorrow') {
                    value = getShiftedDate(1);
                }

                if (dateFromInput) {
                    dateFromInput.value = value;
                }

                if (dateToInput) {
                    dateToInput.value = value;
                }

                updateQuickDateState();
                resetPageToFirst();
                form.submit();
            });
        });

        if (dateFromInput) {
            dateFromInput.addEventListener('change', updateQuickDateState);
            dateFromInput.addEventListener('input', updateQuickDateState);
        }

        if (dateToInput) {
            dateToInput.addEventListener('change', updateQuickDateState);
            dateToInput.addEventListener('input', updateQuickDateState);
        }

        if (pageSizeSelect) {
            pageSizeSelect.addEventListener('change', function () {
                if (currentPageSizeInput) {
                    currentPageSizeInput.value = currentPageSizeInput.value || pageSizeSelect.value;
                }
                form.submit();
            });
        }

        if (resetBtn) {
            resetBtn.addEventListener('click', function () {
                window.location.href = window.location.pathname;
            });
        }

        updateQuickDateState();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();