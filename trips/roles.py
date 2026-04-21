"""
Домен ролей рейса.

Единый источник истины для ответа на вопрос «какую роль играет
организация-наблюдатель в данном рейсе?». Функция чистая и не знает
ни о Django, ни о БД — её легко тестировать и реиспользовать.

Используется из:
    * Trip.perspective()        — для сохранённого рейса;
    * TripCreateView / TripUpdateView — для рендера формы (передать роль
      в контекст заранее, чтобы UI не гадал);
    * trip_form_role.js         — зеркалирует эту же логику на клиенте
      для мгновенной реакции UI на изменение полей формы (без
      round-trip'а на сервер).

Если добавляете сюда новый вариант роли — обязательно обновите JS-зеркало
в static/trips/js/trip_form_role.js и добавьте тесты в обоих местах.
"""

from __future__ import annotations

from django.db import models


class TripRole(models.TextChoices):
    """
    Роль организации-наблюдателя относительно конкретного рейса.

    Значения синхронизированы со строками, которые возвращает
    Trip.perspective()['role'] — менять их без миграции данных нельзя,
    они попадают в UI-шаблоны и JS.
    """

    CLIENT = "client", "Заказчик"
    CARRIER = "carrier", "Перевозчик"
    FORWARDER = "forwarder", "Экспедитор"
    OBSERVER = "observer", "Наблюдатель"


def compute_trip_role(
    *,
    client_id: int | None,
    carrier_id: int | None,
    forwarder_id: int | None,
    viewer_org_id: int | None,
) -> TripRole:
    """
    Возвращает роль viewer_org_id в рейсе (client / carrier / forwarder /
    observer). Pure function: никакого I/O, никаких ORM-вызовов.

    Правила (совпадают с Trip.perspective()):
    - viewer_org_id is None  → OBSERVER
    - viewer_org_id == forwarder_id  → FORWARDER
      (проверяется первым: экспедитор — явная отдельная роль посредника.
       validate_forwarder запрещает совпадение forwarder с client/carrier,
       так что коллизии невозможны; порядок сохранён для идентичности
       с Trip.perspective())
    - viewer_org_id == client_id  → CLIENT
    - viewer_org_id == carrier_id  → CARRIER
    - иначе  → OBSERVER

    Важное следствие для internal-рейса (client и carrier — обе свои,
    разные org): perspective зависит от viewer — для client-own
    вернётся CLIENT, для carrier-own — CARRIER. Это консистентно с
    validate_costs_by_our_company_role, где обе стоимости разрешены.

    Все аргументы — keyword-only, чтобы исключить ошибки порядка:
    client_id vs carrier_id с одинаковыми типами — классическая ловушка.
    """
    if viewer_org_id is None:
        return TripRole.OBSERVER

    if forwarder_id is not None and viewer_org_id == forwarder_id:
        return TripRole.FORWARDER

    if client_id is not None and viewer_org_id == client_id:
        return TripRole.CLIENT

    if carrier_id is not None and viewer_org_id == carrier_id:
        return TripRole.CARRIER

    return TripRole.OBSERVER
