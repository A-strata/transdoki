(function () {
    const CATEGORIES = ['A', 'B', 'C', 'D', 'M', 'BE', 'CE', 'DE'];
    const group = document.getElementById('cat-btn-group');
    const input = document.getElementById('id_license_categories');
    if (!group || !input) return;

    const selected = new Set(
        (input.value || '').split(',').map(s => s.trim()).filter(Boolean)
    );

    function syncInput() {
        input.value = CATEGORIES.filter(c => selected.has(c)).join(', ');
    }

    CATEGORIES.forEach(cat => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'cat-btn' + (selected.has(cat) ? ' active' : '');
        btn.textContent = cat;
        btn.addEventListener('click', () => {
            if (selected.has(cat)) {
                selected.delete(cat);
                btn.classList.remove('active');
            } else {
                selected.add(cat);
                btn.classList.add('active');
            }
            syncInput();
        });
        group.appendChild(btn);
    });

    syncInput();
})();
