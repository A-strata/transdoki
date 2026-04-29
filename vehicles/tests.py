"""
Тесты AJAX-поиска транспортных средств (vehicles:search → VehicleSearchView).

Endpoint возвращает единый JSON-контракт (transdoki/search.py):
    {"items": [...], "groups"?: [...], "hint"?: {...}}

VehicleSearchView работает в strict_carrier-режиме: при наличии
`carrier_id` выдача жёстко ограничивается машинами этого перевозчика
(одинаково для своих и внешних фирм). Это зеркалит серверный валидатор
`validate_vehicles_belong_to_carrier`: truck.owner == carrier.

Сценарии:
  - фильтр по type=truck / type=trailer,
  - own=1 (только ТС «наших» фирм),
  - carrier_id (strict): свой/внешний перевозчик с машинами и без,
  - поиск по grn / brand,
  - tenant-изоляция,
  - невалидный carrier_id трактуется как отсутствие.
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import Account
from organizations.models import Organization
from vehicles.models import Vehicle, VehicleType

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["*"])
class VehicleSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="vehsearch", password="x")
        cls.account = Account.objects.create(name="Acc", owner=cls.user)
        cls.user.profile.account = cls.account
        cls.user.profile.save(update_fields=["account"])

        cls.own_carrier = Organization.objects.create(
            account=cls.account, full_name="ООО Мой Парк", short_name="МойПарк",
            inn="7707083893", is_own_company=True,
        )
        cls.ext_carrier = Organization.objects.create(
            account=cls.account, full_name="ООО Клиент", short_name="Клиент",
            inn="7728168971", is_own_company=False,
        )

        cls.own_truck = Vehicle.objects.create(
            account=cls.account, grn="А001АА777", brand="MAN",
            vehicle_type=VehicleType.TRUCK, owner=cls.own_carrier,
        )
        cls.own_trailer = Vehicle.objects.create(
            account=cls.account, grn="АА0001_77", brand="Krone",
            vehicle_type=VehicleType.TRAILER, owner=cls.own_carrier,
        )
        cls.ext_truck = Vehicle.objects.create(
            account=cls.account, grn="В002ВВ777", brand="Volvo",
            vehicle_type=VehicleType.TRUCK, owner=cls.ext_carrier,
        )

    def setUp(self):
        self.c = Client()
        self.c.force_login(self.user)

    def _search(self, **params):
        url = reverse("vehicles:search")
        return self.c.get(url, params).json()

    def test_flat_response_without_params(self):
        data = self._search()
        ids = {it["id"] for it in data["items"]}
        self.assertEqual(ids, {self.own_truck.pk, self.own_trailer.pk, self.ext_truck.pk})
        self.assertNotIn("groups", data)

    def test_type_truck_filter_excludes_trailers(self):
        data = self._search(type="truck")
        ids = {it["id"] for it in data["items"]}
        self.assertIn(self.own_truck.pk, ids)
        self.assertIn(self.ext_truck.pk, ids)
        self.assertNotIn(self.own_trailer.pk, ids)

    def test_type_trailer_filter(self):
        data = self._search(type="trailer")
        ids = [it["id"] for it in data["items"]]
        self.assertEqual(ids, [self.own_trailer.pk])

    def test_own_filter_excludes_external_owner_vehicles(self):
        data = self._search(**{"own": "1"})
        ids = {it["id"] for it in data["items"]}
        self.assertIn(self.own_truck.pk, ids)
        self.assertIn(self.own_trailer.pk, ids)
        self.assertNotIn(self.ext_truck.pk, ids)

    def test_own_carrier_without_query_single_group(self):
        data = self._search(carrier_id=self.own_carrier.pk, type="truck")
        self.assertEqual(len(data["groups"]), 1)
        self.assertEqual(data["groups"][0]["key"], "carrier")
        self.assertIsNone(data["groups"][0]["label"])
        ids = [it["id"] for it in data["items"]]
        self.assertEqual(ids, [self.own_truck.pk])
        self.assertNotIn("hint", data)

    def test_own_carrier_with_query_only_carrier_group_no_others(self):
        # Strict-режим: даже когда поисковый запрос мог бы зацепить машины
        # других перевозчиков (q="0" матчит и А001АА777, и В002ВВ777),
        # дропдаун должен показать ТОЛЬКО машины выбранного перевозчика.
        # Никакой группы «Другие» — серверный валидатор всё равно отвергнет.
        data = self._search(carrier_id=self.own_carrier.pk, q="0", type="truck")
        self.assertEqual([g["key"] for g in data["groups"]], ["carrier"])
        ids = [it["id"] for it in data["items"]]
        self.assertEqual(ids, [self.own_truck.pk])
        self.assertNotIn(self.ext_truck.pk, ids)

    def test_external_carrier_filtered_strictly_to_own_vehicles(self):
        # «Наша фирма — заказчик»: перевозчик внешний (is_own_company=False).
        # Strict-режим обязан отдать только машины этого перевозчика, без
        # fallback'а на плоский список и без warning-хинта. Раньше здесь
        # возвращался весь справочник + хинт «Не привязаны к перевозчику».
        data = self._search(carrier_id=self.ext_carrier.pk)
        ids = [it["id"] for it in data["items"]]
        self.assertEqual(ids, [self.ext_truck.pk])
        self.assertEqual([g["key"] for g in data["groups"]], ["carrier"])
        self.assertNotIn("hint", data)
        self.assertNotIn(self.own_truck.pk, ids)
        self.assertNotIn(self.own_trailer.pk, ids)

    def test_carrier_without_vehicles_returns_empty_with_info_hint(self):
        # У перевозчика нет ни одной машины и пользователь ничего не ищет —
        # отдаём пустой список + info-хинт с именем перевозчика. Фронт
        # на это нарисует empty-state и футер «+ Добавить ТС». Сценарий
        # одинаков для своих и внешних перевозчиков (проверяем оба).
        empty_own = Organization.objects.create(
            account=self.account, full_name="ООО Пустой Свой",
            short_name="ПустойСвой", inn="7736050003", is_own_company=True,
        )
        data = self._search(carrier_id=empty_own.pk)
        self.assertEqual(data["items"], [])
        self.assertNotIn("groups", data)
        self.assertEqual(data["hint"]["type"], "info")
        self.assertIn("ПустойСвой", data["hint"]["text"])
        self.assertIn("ни одной машины", data["hint"]["text"])

        empty_ext = Organization.objects.create(
            account=self.account, full_name="ООО Пустой Внешний",
            short_name="ПустойВнешний", inn="7704217370", is_own_company=False,
        )
        data = self._search(carrier_id=empty_ext.pk)
        self.assertEqual(data["items"], [])
        self.assertEqual(data["hint"]["type"], "info")
        self.assertIn("ПустойВнешний", data["hint"]["text"])

    def test_empty_carrier_hint_is_field_aware_truck_vs_trailer(self):
        # Поле «Автомобиль» (type=truck) и поле «Прицеп» (type=trailer)
        # должны давать разный текст хинта — про машину и про прицеп
        # соответственно. Один и тот же перевозчик у обоих.
        empty_own = Organization.objects.create(
            account=self.account, full_name="ООО Пустой Свой",
            short_name="ПустойСвой", inn="7736050003", is_own_company=True,
        )

        data = self._search(carrier_id=empty_own.pk, type="truck")
        self.assertIn("ни одной машины", data["hint"]["text"])
        self.assertNotIn("прицеп", data["hint"]["text"].lower())

        data = self._search(carrier_id=empty_own.pk, type="trailer")
        self.assertIn("ни одного прицепа", data["hint"]["text"])
        self.assertNotIn("машин", data["hint"]["text"].lower())

        # Без type — fallback к формулировке про машину (нормальный путь
        # из формы рейса всегда передаёт type, но поведение фиксируем).
        data = self._search(carrier_id=empty_own.pk)
        self.assertIn("ни одной машины", data["hint"]["text"])

    def test_carrier_with_query_no_match_returns_empty_without_hint(self):
        # У перевозчика есть машины, но q не совпадает ни с одной — пустой
        # список БЕЗ хинта. Фронт нарисует обычный empty-state из
        # ENTITY_DEFAULTS (с предложением проверить написание / создать).
        data = self._search(carrier_id=self.own_carrier.pk, q="ZZZZZZ")
        self.assertEqual(data["items"], [])
        self.assertNotIn("groups", data)
        self.assertNotIn("hint", data)

    def test_invalid_carrier_id_falls_back_to_flat(self):
        # garbage в carrier_id трактуется как отсутствие → плоский ответ
        # без группировки и без хинтов.
        data = self._search(carrier_id="garbage")
        self.assertNotIn("groups", data)
        self.assertNotIn("hint", data)
        ids = {it["id"] for it in data["items"]}
        self.assertEqual(ids, {self.own_truck.pk, self.own_trailer.pk, self.ext_truck.pk})

    def test_nonexistent_carrier_id_falls_back_to_flat(self):
        # carrier_id указывает на несуществующую организацию (или из чужого
        # аккаунта — for_account её отсечёт одинаково) — strict-режим отдаёт
        # плоский ответ без хинтов и группировки. Серверная валидация при
        # сабмите всё равно отвергнет такую попытку.
        data = self._search(carrier_id=999999)
        self.assertNotIn("groups", data)
        self.assertNotIn("hint", data)
        ids = {it["id"] for it in data["items"]}
        self.assertEqual(ids, {self.own_truck.pk, self.own_trailer.pk, self.ext_truck.pk})

    def test_search_by_grn_and_brand(self):
        self.assertEqual(
            [it["id"] for it in self._search(q="MAN")["items"]],
            [self.own_truck.pk],
        )
        # Поиск по части GRN
        self.assertIn(
            self.own_trailer.pk,
            [it["id"] for it in self._search(q="АА000")["items"]],
        )

    def test_tenant_isolation(self):
        other_user = User.objects.create_user(username="other", password="x")
        other_account = Account.objects.create(name="Other", owner=other_user)
        other_user.profile.account = other_account
        other_user.profile.save(update_fields=["account"])

        c = Client()
        c.force_login(other_user)
        data = c.get(reverse("vehicles:search")).json()
        self.assertEqual(data["items"], [])
