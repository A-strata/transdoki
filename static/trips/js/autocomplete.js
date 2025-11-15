function initAutocomplete(selectId) {
    const select = document.getElementById(selectId);
    if (!select) {
        console.warn(`Element ${selectId} not found`);
        return;
    }

    const container = document.createElement('div');
    container.style.position = 'relative';
    container.style.display = 'inline-block';
    container.className = 'autocomplete-container';
    
    const input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'Начните вводить...';
    input.className = 'autocomplete-input form-control';
    input.style.width = '100%';

    // НЕ создаем скрытое поле - работаем с оригинальным select
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
    dropdown.style.borderTop = 'none';
    dropdown.style.zIndex = '1000';
    dropdown.className = 'autocomplete-dropdown';

    // Вставляем контейнер перед select и перемещаем select внутрь
    select.parentNode.insertBefore(container, select);
    container.appendChild(input);
    container.appendChild(dropdown);
    container.appendChild(select); // Перемещаем select внутрь контейнера
    
    // Скрываем select, но оставляем в DOM
    select.style.position = 'absolute';
    select.style.opacity = '0';
    select.style.height = '1px';
    select.style.width = '1px';
    select.style.pointerEvents = 'none';
    select.style.zIndex = '-1';

    console.log(`Autocomplete initialized for ${selectId}, select name: ${select.name}`);

    // Восстанавливаем значение при загрузке
    function syncInputToSelect() {
        if (select.value) {
            const selectedOption = select.options[select.selectedIndex];
            if (selectedOption && selectedOption.text) {
                input.value = selectedOption.text;
                console.log(`Initialized ${selectId} with:`, selectedOption.text, select.value);
            }
        } else {
            input.value = '';
        }
    }

    // Синхронизация при изменении select (на случай если значение меняется извне)
    select.addEventListener('change', syncInputToSelect);
    
    // Инициализация
    syncInputToSelect();

    function updateDropdown() {
        const searchTerm = input.value.toLowerCase().trim();
        dropdown.innerHTML = '';
        
        let hasResults = false;
        let exactMatch = null;
        
        for (let option of select.options) {
            if (!option.value) continue;
            
            const text = option.textContent.toLowerCase();
            if (text.includes(searchTerm)) {
                const item = document.createElement('div');
                item.textContent = option.text;
                item.style.padding = '8px 12px';
                item.style.cursor = 'pointer';
                item.style.borderBottom = '1px solid #eee';
                
                // Запоминаем точное совпадение
                if (text === searchTerm.toLowerCase()) {
                    exactMatch = option;
                }
                
                item.addEventListener('click', function() {
                    selectOption(option);
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
        
        // Автоматически выбираем точное совпадение
        if (exactMatch && searchTerm.length > 0) {
            selectOption(exactMatch);
        } else {
            dropdown.style.display = searchTerm && hasResults ? 'block' : 'none';
        }
    }

    function selectOption(option) {
        input.value = option.text;
        select.value = option.value;
        dropdown.style.display = 'none';
        
        console.log(`Selected ${selectId}:`, option.text, option.value);
        
        // Триггерим события для Django
        const changeEvent = new Event('change', { bubbles: true });
        const inputEvent = new Event('input', { bubbles: true });
        select.dispatchEvent(changeEvent);
        select.dispatchEvent(inputEvent);
        
        // Также диспатчим события на input для хорошей меры
        input.dispatchEvent(changeEvent);
        input.dispatchEvent(inputEvent);
    }

    input.addEventListener('input', function() {
        // Если пользователь очищает поле, очищаем и select
        if (!input.value.trim()) {
            select.value = '';
            const changeEvent = new Event('change', { bubbles: true });
            select.dispatchEvent(changeEvent);
        }
        updateDropdown();
    });
    
    input.addEventListener('focus', function() {
        updateDropdown();
        // Показываем все варианты при фокусе
        if (!input.value.trim()) {
            const searchTerm = '';
            dropdown.innerHTML = '';
            
            for (let option of select.options) {
                if (!option.value) continue;
                
                const item = document.createElement('div');
                item.textContent = option.text;
                item.style.padding = '8px 12px';
                item.style.cursor = 'pointer';
                item.style.borderBottom = '1px solid #eee';
                
                item.addEventListener('click', function() {
                    selectOption(option);
                });
                
                item.addEventListener('mouseenter', function() {
                    this.style.background = '#f5f5f5';
                });
                
                item.addEventListener('mouseleave', function() {
                    this.style.background = 'white';
                });
                
                dropdown.appendChild(item);
            }
            dropdown.style.display = 'block';
        }
    });

    input.addEventListener('blur', function() {
        // Не скрываем сразу, чтобы можно было кликнуть по варианту
        setTimeout(() => {
            dropdown.style.display = 'none';
        }, 200);
    });

    // Скрываем dropdown при клике вне
    document.addEventListener('click', function(e) {
        if (!container.contains(e.target)) {
            dropdown.style.display = 'none';
        }
    });

    // Enter для выбора первого варианта
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            if (dropdown.style.display === 'block') {
                const firstItem = dropdown.querySelector('div');
                if (firstItem) {
                    firstItem.click();
                }
            }
            e.preventDefault();
        }
        
        // Esc для скрытия dropdown
        if (e.key === 'Escape') {
            dropdown.style.display = 'none';
            input.blur();
        }
    });

    // Обновляем dropdown при изменении select извне
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'attributes' && mutation.attributeName === 'value') {
                syncInputToSelect();
            }
        });
    });
    
    observer.observe(select, { attributes: true, attributeFilter: ['value'] });
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Initializing autocomplete...');
    
    // Используем правильные ID полей Django
    const fields = [
        'id_client', 'id_consignor', 'id_consignee', 
        'id_carrier', 'id_driver', 'id_truck', 'id_trailer'
    ];
    
    fields.forEach(fieldId => {
        // Добавляем небольшую задержку для полной загрузки DOM
        setTimeout(() => {
            initAutocomplete(fieldId);
        }, 100);
    });
    
    // Отладочная функция для проверки состояния полей
    window.debugFormState = function() {
        console.log('=== FORM STATE DEBUG ===');
        const fields = ['client', 'consignor', 'consignee', 'carrier', 'driver', 'truck', 'trailer'];
        fields.forEach(fieldName => {
            const select = document.getElementById(`id_${fieldName}`);
            const input = document.querySelector(`#id_${fieldName}`).parentNode.querySelector('.autocomplete-input');
            console.log(`${fieldName}:`, {
                selectValue: select?.value,
                inputValue: input?.value,
                selectName: select?.name,
                selectInDOM: !!select
            });
        });
    };
});