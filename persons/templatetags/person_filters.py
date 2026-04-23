from django import template
from django.utils.html import format_html

register = template.Library()


def _pretty_phone(value):
    """Возвращает (e164, pretty) или (None, original) если номер не распознан.

    Общий парсер для фильтра и тега — чтобы они расходились только в
    упаковке результата (текст vs HTML), а не в правилах форматирования.
    """
    if not value:
        return None, ""
    digits = "".join(filter(str.isdigit, str(value)))
    if len(digits) == 11 and digits.startswith("7"):
        pretty = f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
        return digits, pretty
    return None, str(value)


@register.filter
def phone_format(value):
    """Форматирует 79001234567 → +7 (900) 123-45-67.

    Оставлен для обратной совместимости со старыми шаблонами. В новых
    шаблонах предпочтительнее тег ``{% phone_link %}``: он даёт
    кликабельную ``tel:`` ссылку, корректный aria-label и единый
    empty-state.
    """
    if not value:
        return "—"
    _, pretty = _pretty_phone(value)
    return pretty


@register.simple_tag
def phone_link(value, empty="—"):
    """Рендерит номер как кликабельную ``tel:`` ссылку.

    Использование::

        {% phone_link person.phone %}
        {% phone_link contact.phone empty="Телефон не указан" %}

    Поведение:
      * пусто → ``<span class="tms-phone tms-phone--empty">{empty}</span>``;
      * валидный российский номер → ``<a class="tms-phone" href="tel:+7...">``
        с aria-label «Позвонить: +7 (999) ...»;
      * номер в нераспознанном формате → текст без ссылки (fallback),
        чтобы не отдавать в ``tel:`` мусор.

    Кликабельность номера — ключевая ценность карточки: диспетчеру не
    нужно выделять-копировать, софтфон на desktop или звонилка на
    мобильном ловят ссылку напрямую.
    """
    digits, pretty = _pretty_phone(value)
    if not value:
        return format_html('<span class="tms-phone tms-phone--empty">{}</span>', empty)
    if digits is None:
        # Номер не в каноничном формате — не рискуем подставлять в tel:,
        # отдаём как есть, чтобы пользователь хотя бы увидел значение.
        return format_html('<span class="tms-phone">{}</span>', pretty)
    return format_html(
        '<a class="tms-phone" href="tel:+{digits}" aria-label="Позвонить: {pretty}">{pretty}</a>',
        digits=digits,
        pretty=pretty,
    )
