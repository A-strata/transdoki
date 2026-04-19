"""Фильтры шаблонов для биллинга."""
from django import template

register = template.Library()


@register.filter
def dict_lookup(mapping, key):
    """
    Получить значение из словаря по ключу в шаблоне.
    Применение: {{ plan_names|dict_lookup:bp.plan_code }}
    Возвращает None если ключ отсутствует или значение — не словарь.
    """
    if not isinstance(mapping, dict):
        return None
    return mapping.get(key)
