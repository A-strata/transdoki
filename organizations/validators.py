from django.core.exceptions import ValidationError


def validate_inn(value):
    """
    Валидатор ИНН с проверкой контрольной суммы
    """
    if not value:
        raise ValidationError('ИНН пуст')

    if not value.isdigit():
        raise ValidationError('ИНН может состоять только из цифр')

    if len(value) not in [10, 12]:
        raise ValidationError('ИНН может состоять только из 10 или 12 цифр')

    def check_digit(inn, coefficients):
        n = 0
        for i, coef in enumerate(coefficients):
            n += coef * int(inn[i])
        return n % 11 % 10

    # Проверка контрольной суммы
    if len(value) == 10:
        n10 = check_digit(value, [2, 4, 10, 3, 5, 9, 4, 6, 8])
        if n10 != int(value[9]):
            raise ValidationError('Неправильное контрольное число')

    elif len(value) == 12:
        n11 = check_digit(value, [7, 2, 4, 10, 3, 5, 9, 4, 6, 8])
        n12 = check_digit(value, [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8])
        if n11 != int(value[10]) or n12 != int(value[11]):
            raise ValidationError('Неправильное контрольное число')
