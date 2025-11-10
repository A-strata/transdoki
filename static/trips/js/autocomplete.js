function initAutocomplete(selectId) {
    const select = document.getElementById(selectId);
    const input = document.createElement('input');
    
    input.type = 'text';
    input.placeholder = 'Начните вводить...';
    input.className = 'autocomplete-input';
    input.style.width = '300px'; // inline backup
    select.parentNode.insertBefore(input, select);
    select.style.display = 'none';
    
    input.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        const options = select.options;
        
        for (let option of options) {
            const text = option.textContent.toLowerCase();
            option.style.display = text.includes(searchTerm) ? '' : 'none';
        }
        
        if (searchTerm.trim() !== '') {
            select.style.display = 'block';
            select.size = Math.min(options.length, 10);
        } else {
            select.style.display = 'none';
        }
    });
    
    select.addEventListener('change', function() {
        input.value = this.options[this.selectedIndex].text;
        this.style.display = 'none';
    });
    
    input.addEventListener('blur', function() {
        select.style.display = 'none';
    });
}

document.addEventListener('DOMContentLoaded', function() {
    initAutocomplete('id_client');
    initAutocomplete('id_consignor');
    initAutocomplete('id_consignee');
    initAutocomplete('id_carrier');
    initAutocomplete('id_driver');
    initAutocomplete('id_truck');
    initAutocomplete('id_trailer');
});