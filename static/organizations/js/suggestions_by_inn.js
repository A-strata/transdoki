document.addEventListener('DOMContentLoaded', function() {
    const fillButton = document.getElementById('btn_fill_inn');
    
    fillButton.addEventListener('click', function() {
        const inn = document.getElementById('id_inn').value;  // ✅ Просто id_inn
        
        if (inn.length !== 10 && inn.length !== 12) {
            alert('Пожалуйста, введите корректный ИНН (10 или 12 цифр).');
            return;
        }
        
        fetch(`/organizations/api/suggestions_by_inn/?inn=${inn}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert(data.error);
                    return;
                }
                
                // ✅ Стандартные ID полей Django
                document.getElementById('id_full_name').value = data.full_name || '';
                document.getElementById('id_short_name').value = data.short_name || '';
                document.getElementById('id_address').value = data.address || '';
                document.getElementById('id_ogrn').value = data.ogrn || '';
                document.getElementById('id_kpp').value = data.kpp || '';
            })
            .catch(error => {
                alert('Произошла ошибка при получении данных');
            });
    });
});