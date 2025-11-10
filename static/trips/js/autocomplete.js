// static/trips/js/autocomplete.js
function initAutocomplete(selectId) {
    const select = document.getElementById(selectId);
    const input = document.createElement('input');
    
    // Заменяем select на input
    input.type = 'text';
    input.placeholder = 'Начните вводить...';
    input.style.width = '100%';
    select.parentNode.insertBefore(input, select);
    select.style.display = 'none';
    
    // Поиск и фильтрация
    input.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        const options = select.options;
        
        for (let option of options) {
            const text = option.textContent.toLowerCase();
            option.style.display = text.includes(searchTerm) ? '' : 'none';
        }
        
        // Показываем select для выбора
        select.style.display = 'block';
        select.size = Math.min(options.length, 10); // показываем до 10 вариантов
    });
    
    // Выбор варианта
    select.addEventListener('change', function() {
        input.value = this.options[this.selectedIndex].text;
        this.style.display = 'none';
    });
    
    // Скрываем при потере фокуса
    input.addEventListener('blur', function() {
        setTimeout(() => select.style.display = 'none', 200);
    });
}

// Инициализация для всех нужных полей
document.addEventListener('DOMContentLoaded', function() {
    initAutocomplete('id_client');
    initAutocomplete('id_consignor');
    initAutocomplete('id_consignee');
    initAutocomplete('id_carrier');
    initAutocomplete('id_driver');
});