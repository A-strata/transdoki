"""
AJAX-search endpoints для autocomplete-полей форм.

Единый контракт JSON-ответа:

    {
        "items":  [{"id": int, "text": str, "group"?: str}, ...],
        "groups"?: [{"key": str, "label": str | None}, ...],
        "hint"?:  {"type": "info" | "warning", "text": str},
    }

Правила:
  - `items` — всегда массив; поле `group` у элемента опционально.
  - `groups` — опциональна. Если её нет — items рендерятся плоско.
    Если есть — порядок групп задаёт порядок рендера; `label = None`
    означает безымянную группу (без заголовка).
  - `hint` — опциональна, одна на ответ (подсказка над списком).

Контракт единый для всех search-view'ов (Organization, Person,
Vehicle, Trip, …). JS-клиент `static/js/autocomplete.js` → `renderResponse`
обрабатывает именно эту структуру.

Базовый класс `AjaxSearchView`:
  - tenant-изоляция встроена (get_queryset → for_account).
  - стандартный поиск по search_fields (icontains OR-join, многословный q
    интерпретируется как AND между словами).
  - сериализация через str(obj) по умолчанию; переопределяется
    `serialize_item(obj)`.
  - подкласс может переопределить `apply_extra_filters(qs)` для доп.
    GET-фильтров и `build_response(qs)` для группировки/хинтов.

Миксин `CarrierGroupingMixin` реализует типовой случай «разделить выдачу
на записи, связанные с выбранным перевозчиком, и остальные».
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from django.contrib.auth.decorators import login_required
from django.db.models import Q, QuerySet
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_GET

from transdoki.tenancy import get_request_account


@dataclass(frozen=True)
class SearchGroup:
    """Группа в JSON-ответе.

    key    — стабильный идентификатор (совпадает со значением `group` у items).
    label  — заголовок группы в UI; None = безымянная группа (рендерится
             без видимого заголовка, например первая группа «carrier»).
    """

    key: str
    label: str | None = None


@dataclass(frozen=True)
class SearchHint:
    """Подсказка над списком результатов.

    type — "info" | "warning" (влияет на стилистику).
    text — готовый текст для пользователя.
    """

    type: str
    text: str


@method_decorator([login_required, require_GET], name="dispatch")
class AjaxSearchView(View):
    """Базовый CBV для AJAX-поиска autocomplete-полей.

    Подкласс задаёт:
        model         — Django-модель (наследник UserOwnedModel).
        search_fields — tuple имён полей для icontains-поиска.
        order_by      — tuple полей ORDER BY.
        limit         — сколько записей возвращать (default 25).

    При необходимости переопределяет:
        apply_extra_filters(qs) — доп. GET-фильтры (own=1, type=...).
        serialize_item(obj)     — форматирование одного item'а в dict.
        build_response(qs)      — для сценариев с группами/хинтами;
                                  по умолчанию — плоский список.
    """

    model = None
    search_fields: Sequence[str] = ()
    order_by: Sequence[str] = ()
    # Суммарный лимит items в ответе. 10 — практический потолок для
    # autocomplete на ноутбучном форм-факторе: больше пользователь всё
    # равно не просматривает, а поиск уточняет запросом. Срезает DB- и
    # network-cost на больших справочниках. Для группированных ответов
    # (CarrierGroupingMixin) лимит применяется ко всему ответу, не
    # поштучно к каждой группе.
    limit: int = 10

    # ── Hooks for subclasses ────────────────────────────────────────────

    def get_queryset(self) -> QuerySet:
        """Tenant-фильтрованный queryset + дополнительные фильтры подкласса.

        Имя `get_queryset` (а не `get_base_queryset`) выбрано сознательно:
        это Django-конвенция и одновременно маркер для
        tests.test_tenant_isolation, который ищет в исходном коде метода
        слово "account".
        """
        qs = self.model.objects.for_account(get_request_account(self.request))
        qs = self.apply_extra_filters(qs)
        return qs

    def apply_extra_filters(self, qs: QuerySet) -> QuerySet:
        """Переопределить в подклассе для own=1 / type=... / exclude=... и пр."""
        return qs

    def apply_search(self, qs: QuerySet, q: str) -> QuerySet:
        """Стандартный OR-поиск по self.search_fields.

        Многословный q интерпретируется как AND: каждое слово должно
        найтись хотя бы в одном из self.search_fields. Это даёт ожидаемое
        поведение для ФИО («Иванов Петрович» → И+Л в разных полях).
        """
        if not q or not self.search_fields:
            return qs
        for part in q.split():
            cond = Q()
            for field in self.search_fields:
                cond |= Q(**{f"{field}__icontains": part})
            qs = qs.filter(cond)
        return qs

    def serialize_item(self, obj) -> dict:
        return {"id": obj.pk, "text": str(obj)}

    def build_response(self, qs: QuerySet) -> dict:
        """По умолчанию — плоский ответ без групп и без хинта.

        Возвращает dict с обязательным ключом "items" и опциональными
        "groups" (Sequence[SearchGroup]) и "hint" (SearchHint).
        """
        items = [
            self.serialize_item(o)
            for o in qs.order_by(*self.order_by)[: self.limit]
        ]
        return {"items": items}

    # ── Implementation ─────────────────────────────────────────────────

    def get(self, request, *args, **kwargs):
        qs = self.get_queryset()
        q = request.GET.get("q", "").strip()
        qs = self.apply_search(qs, q)

        payload = self.build_response(qs)
        out: dict = {"items": payload["items"]}

        groups = payload.get("groups")
        if groups:
            out["groups"] = [
                {"key": g.key, "label": g.label} for g in groups
            ]

        hint = payload.get("hint")
        if hint is not None:
            out["hint"] = {"type": hint.type, "text": hint.text}

        return JsonResponse(out)


class CarrierGroupingMixin:
    """Группировка выдачи по связи с выбранным перевозчиком.

    Два режима, переключаемые атрибутом подкласса `strict_carrier`.

    ── Non-strict (default, используется для Person / водителей) ──────
    Сценарий: в форме рейса уже выбран «наш» перевозчик, и для поля
    driver пользователь хочет видеть сначала водителей этого перевозчика,
    а потом — остальных. Жёсткой связи водителя с перевозчиком на уровне
    модели нет (водителя могут «одолжить»), поэтому «Другие» — допустимый
    вариант выбора.

    Поведение non-strict:
      1. carrier_id не задан                → плоский ответ.
      2. carrier_id невалиден / не нашёлся
         в аккаунте / не is_own_company     → плоский ответ + warning-hint.
      3. carrier_id валиден, own_company:
         3a. в carrier_qs ничего нет, q пуст → плоский ответ по полной
             базе + warning-hint (группировка бессмысленна).
         3b. q пуст  → группа "carrier" без заголовка.
         3c. q задан → группы "carrier" (без заголовка) и "others"
             (заголовок «Другие»).

    ── Strict (используется для Vehicle / ТС) ─────────────────────────
    Сценарий: в форме рейса для truck/trailer действует жёсткое правило
    `validate_vehicles_belong_to_carrier` (truck.owner == carrier). Любая
    выдача, выходящая за этот критерий, ведёт к ошибке валидации на
    сабмите — поэтому показываем ТОЛЬКО машины перевозчика. Гейт
    `is_own_company` здесь не применяется: правило одинаково для своих и
    внешних перевозчиков. Если у перевозчика нет машин — отдаём пустой
    список с info-хинтом, фронт нарисует empty-state и предложит создать
    новое ТС (quick-create уже подставит правильного владельца).

    Поведение strict:
      1. carrier_id не задан / невалиден / не из аккаунта
                                                  → плоский ответ.
      2. carrier_id валиден, у перевозчика есть машины (с учётом q)
                                                  → группа "carrier".
      3. carrier_id валиден, машин нет:
         3a. q пуст                               → пустой список +
             info-хинт «У перевозчика «X» пока нет ни одной машины».
         3b. q задан (просто не нашлось)          → пустой список без
             хинта; фронт покажет стандартное empty-state.

    Подкласс задаёт:
        owner_field — имя FK-поля модели, указывающего на Organization:
                      "employer" для Person, "owner" для Vehicle.
    """

    owner_field: str = ""

    # Включает strict-режим (см. docstring класса). Для Vehicle = True.
    strict_carrier: bool = False

    # Текст хинта (non-strict) — когда группировка бессмысленна и мы
    # вынуждены показать всю базу.
    no_link_hint_text: str = "Не привязаны к перевозчику — показаны все"

    # Шаблон info-хинта (strict) — когда у выбранного перевозчика нет
    # ни одной связанной записи и пользователь ничего не ищет. {carrier}
    # — строковое представление организации (Organization.__str__ →
    # short_name). Подкласс может переопределить либо сам шаблон, либо
    # метод format_empty_carrier_hint() ниже — последнее нужно, когда
    # формулировка зависит от параметров запроса (например, разный текст
    # для type=truck и type=trailer в VehicleSearchView).
    empty_carrier_hint_text: str = (
        "У перевозчика «{carrier}» пока нет связанных записей"
    )

    def format_empty_carrier_hint(self, carrier) -> str:
        """Текст info-хинта для перевозчика без связанных записей.

        По умолчанию подставляет {carrier} в self.empty_carrier_hint_text.
        Переопределение в подклассе позволяет выбрать формулировку по
        контексту запроса (например, type=truck vs type=trailer)."""
        return self.empty_carrier_hint_text.format(carrier=str(carrier))

    def filter_carrier_qs(self, qs: QuerySet, carrier) -> QuerySet:
        """В strict-режиме — queryset записей, считающихся «связанными
        с перевозчиком».

        По умолчанию — точное совпадение по owner_field_id. Подкласс
        может расширить семантику: например, для Person FK
        Person.employer допускает NULL by design (фрилансер без
        работодателя в справочнике), и такие водители разумно показывать
        при любом перевозчике."""
        return qs.filter(**{f"{self.owner_field}_id": carrier.pk})

    def build_response(self, qs: QuerySet) -> dict:
        # Поздний импорт: избегаем circular import между
        # transdoki.search и organizations.models.
        from organizations.models import Organization

        request = self.request
        q = request.GET.get("q", "").strip()
        carrier_id_raw = request.GET.get("carrier_id", "").strip()

        def flat_items(source_qs, cap=None):
            """Сериализация с лимитом. По умолчанию — self.limit; можно
            передать меньший cap, чтобы поделить бюджет между группами
            (см. случай 3c ниже — carrier получает приоритет, others
            добирают остаток)."""
            n = self.limit if cap is None else cap
            if n <= 0:
                return []
            return [
                self.serialize_item(o)
                for o in source_qs.order_by(*self.order_by)[:n]
            ]

        if not carrier_id_raw.isdigit():
            return {"items": flat_items(qs)}

        account = get_request_account(request)
        carrier = (
            Organization.objects.for_account(account)
            .filter(pk=int(carrier_id_raw))
            .first()
        )

        # ── Strict-режим: жёсткая фильтрация по carrier, без «Других». ──
        if self.strict_carrier:
            if carrier is None:
                # carrier_id указывает на чужой/несуществующий tenant —
                # fallback на плоский ответ. Серверная валидация всё
                # равно отвергнет такую попытку при сабмите.
                return {"items": flat_items(qs)}

            carrier_qs = self.filter_carrier_qs(qs, carrier)
            carrier_items = flat_items(carrier_qs)

            if not carrier_items:
                if not q:
                    # Перевозчик выбран, ничего не ищем — пусто значит
                    # «у этого перевозчика нет ни одной записи».
                    # Хинт + пустой список → фронт рисует empty-state
                    # с футером «+ Добавить».
                    return {
                        "items": [],
                        "hint": SearchHint(
                            type="info",
                            text=self.format_empty_carrier_hint(carrier),
                        ),
                    }
                # q задан, но не нашлось — возвращаем просто пусто;
                # фронт нарисует обычный empty-state из ENTITY_DEFAULTS
                # («…проверьте написание — либо добавьте новое»).
                return {"items": []}

            return {
                "items": [{**it, "group": "carrier"} for it in carrier_items],
                "groups": (SearchGroup(key="carrier"),),
            }

        # ── Non-strict (старая логика, используется для Person). ──────
        if carrier is None or not carrier.is_own_company:
            return {
                "items": flat_items(qs),
                "hint": SearchHint(type="warning", text=self.no_link_hint_text),
            }

        owner_filter = {f"{self.owner_field}_id": carrier.pk}
        carrier_qs = qs.filter(**owner_filter)
        carrier_items = flat_items(carrier_qs)

        # Случай 3a: у «своего» перевозчика ничего не привязано и
        # пользователь ничего не ищет — показываем всю базу с хинтом.
        if not carrier_items and not q:
            return {
                "items": flat_items(qs),
                "hint": SearchHint(type="warning", text=self.no_link_hint_text),
            }

        # Случай 3b: q пуст → одна безымянная группа "carrier".
        if not q:
            return {
                "items": [{**it, "group": "carrier"} for it in carrier_items],
                "groups": (SearchGroup(key="carrier"),),
            }

        # Случай 3c: q задан → carrier + others (с заголовком).
        # Общий лимит — self.limit на обе группы суммарно. Carrier-записи
        # приоритетнее (они семантически ближе к выбранному перевозчику),
        # others добирают оставшийся бюджет. Если carrier уже забрал весь
        # лимит — others пустой, группа «Другие» не рисуется.
        others_budget = self.limit - len(carrier_items)
        others_qs = qs.exclude(**owner_filter)
        others_items = flat_items(others_qs, cap=others_budget)
        groups = [SearchGroup(key="carrier")]
        if others_items:
            groups.append(SearchGroup(key="others", label="Другие"))
        return {
            "items": (
                [{**it, "group": "carrier"} for it in carrier_items]
                + [{**it, "group": "others"} for it in others_items]
            ),
            "groups": tuple(groups),
        }
