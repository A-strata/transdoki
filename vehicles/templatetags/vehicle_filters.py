import re

from django import template

register = template.Library()

# Грузовик/тягач: А123ВЕ77 → А 123 ВЕ 77
_TRUCK_RE = re.compile(r"^([А-ЯЁ])(\d{3})([А-ЯЁ]{2})(\d{2,3})$")
# Прицеп: АВ123477 → АВ 1234 77
_TRAILER_RE = re.compile(r"^([А-ЯЁ]{2})(\d{4})(\d{2,3})$")


@register.filter
def format_grn(value, vehicle_type=""):
    """Форматирует госномер ТС по маске в зависимости от типа.

    Использование: {{ vehicle.grn|format_grn:vehicle.vehicle_type }}
    """
    if not value:
        return "—"
    grn = str(value).upper().strip()
    S = "\u00a0"  # non-breaking space
    if vehicle_type == "trailer":
        m = _TRAILER_RE.match(grn)
        if m:
            return f"{m[1]}{S}{m[2]}{S}{m[3]}"
    else:
        m = _TRUCK_RE.match(grn)
        if m:
            return f"{m[1]}{S}{m[2]}{S}{m[3]}{S}{m[4]}"
    return grn
