"""Доменная логика приложения persons.

Держит единый источник истины для операций, которые используются
в нескольких формах/view. Не зависит от request/view-слоя.
"""

from django.core.exceptions import ValidationError

from .validators import validate_phone_number


def normalize_phone(raw: str) -> str:
    """Нормализует российский номер телефона в формат E.164 без '+'.

    Принимает произвольный ввод: '+7 (999) 123-45-67', '8 999 123 4567',
    '79991234567' и т.п. Возвращает каноничную строку вида '79991234567'.

    Бросает ValidationError, если после зачистки от нецифровых символов
    полученная последовательность не похожа на российский номер.

    Пустой ввод трактуется как некорректный — проверку «поле обязательное/нет»
    делает вызывающий код до вызова normalize_phone().
    """
    digits = "".join(filter(str.isdigit, raw or ""))
    if not digits or digits == "7":
        raise ValidationError("Введите корректный российский номер телефона")
    # '8xxxxxxxxxx' → '7xxxxxxxxxx'
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if len(digits) != 11 or not digits.startswith("7"):
        raise ValidationError("Введите корректный российский номер телефона")
    # Контрольная валидация по модельному инварианту — должна всегда проходить.
    validate_phone_number(digits)
    return digits
