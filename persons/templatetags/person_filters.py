from django import template

register = template.Library()


@register.filter
def phone_format(value):
    """Форматирует 79001234567 → +7 (900) 123-45-67"""
    if not value:
        return "—"
    digits = "".join(filter(str.isdigit, str(value)))
    if len(digits) == 11 and digits.startswith("7"):
        return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return value
