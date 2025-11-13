// trips/static/trips/js/autocomplete.js
function initAutocomplete(selectId) {
    const select = document.getElementById(selectId);
    if (!select) {
        console.warn(`Element ${selectId} not found`);
        return;
    }

    const container = document.createElement('div');
    container.style.position = 'relative';
    container.style.display = 'inline-block';
    
    const input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'Начните вводить...';
    input.className = 'autocomplete-input';
    input.style.width = '300px';

    // Создаем кастомный выпадающий список
    const dropdown = document.createElement('div');
    dropdown.style.display = 'none';
    dropdown.style.position = 'absolute';
    dropdown.style.top = '100%';
    dropdown.style.left = '0';
    dropdown.style.width = '100%';
    dropdown.style.maxHeight = '200px';
    dropdown.style.overflowY = 'auto';
    dropdown.style.background = 'white';
    dropdown.style.border = '1px solid #ccc';
    dropdown.style.zIndex = '1000';
    dropdown.className = 'autocomplete-dropdown';

    // Заменяем select
    select.parentNode.insertBefore(container, select);
    container.appendChild(input);
    container.appendChild(dropdown);
    select.style.display = 'none';

    function updateDropdown() {
        const searchTerm = input.value.toLowerCase();
        dropdown.innerHTML = '';
        
        let hasResults = false;
        
        for (let option of select.options) {
            if (!option.value) continue; // Пропускаем пустые option
            
            const text = option.textContent.toLowerCase();
            if (text.includes(searchTerm)) {
                const item = document.createElement('div');
                item.textContent = option.text;
                item.style.padding = '8px 12px';
                item.style.cursor = 'pointer';
                item.style.borderBottom = '1px solid #eee';
                
                item.addEventListener('click', function() {
                    input.value = option.text;
                    select.value = option.value;
                    dropdown.style.display = 'none';
                    
                    // Триггерим событие change
                    const event = new Event('change', { bubbles: true });
                    select.dispatchEvent(event);
                });
                
                item.addEventListener('mouseenter', function() {
                    this.style.background = '#f5f5f5';
                });
                
                item.addEventListener('mouseleave', function() {
                    this.style.background = 'white';
                });
                
                dropdown.appendChild(item);
                hasResults = true;
            }
        }
        
        dropdown.style.display = searchTerm && hasResults ? 'block' : 'none';
    }

    input.addEventListener('input', updateDropdown);
    input.addEventListener('focus', updateDropdown);

    // Скрываем dropdown при клике вне
    document.addEventListener('click', function(e) {
        if (!container.contains(e.target)) {
            dropdown.style.display = 'none';
        }
    });

    // Enter для выбора первого варианта
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && dropdown.style.display === 'block') {
            const firstItem = dropdown.querySelector('div');
            if (firstItem) {
                firstItem.click();
                e.preventDefault();
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Initializing autocomplete...');
    
    const fields = [
        'id_client', 'id_consignor', 'id_consignee', 
        'id_carrier', 'id_driver', 'id_truck', 'id_trailer'
    ];
    
    fields.forEach(fieldId => {
        initAutocomplete(fieldId);
    });
});