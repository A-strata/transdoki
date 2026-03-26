from django.core.exceptions import ValidationError


def validate_phone_number(value):
    """Проверяет, что номер сохранён в формате E.164: 11 цифр, начинается с 7."""
    if not value:
        return
    if not value.isdigit() or len(value) != 11 or value[0] != '7':
        raise ValidationError('Неверный формат номера телефона')
