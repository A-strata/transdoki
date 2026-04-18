"""Брендинг в печатных формах (колонтитулы и т.п.).

Сейчас подпись показывается всегда. В дальнейшем видимость будет зависеть
от тарифа аккаунта — скрытие подписи станет платной опцией.
"""
from __future__ import annotations


BRANDING_FOOTER_TEXT = "Сформировано в Трансдоки · transdoki.ru"


def branding_footer(account) -> str:
    """Текст для плейсхолдера `{{ branding_footer }}` в печатных шаблонах.

    Возвращает пустую строку, если по тарифу аккаунта брендинг должен быть
    скрыт. Сейчас тарифы не проверяются — подпись показывается всегда.
    """
    # TODO: когда появится тариф «без подписи» — вернуть "" для таких account
    return BRANDING_FOOTER_TEXT


def branding_context(account) -> dict:
    """Контекст для docxtpl: плейсхолдеры брендинга."""
    return {"branding_footer": branding_footer(account)}
