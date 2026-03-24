from django import template

register = template.Library()


@register.filter
def money(value):
    if value is None or value == '':
        return '—'
    try:
        parts = f"{value:.2f}".split('.')
        integer = f"{int(parts[0]):,}".replace(',', '\u00a0')
        return f"{integer},{parts[1]}"
    except (ValueError, TypeError):
        return '—'
