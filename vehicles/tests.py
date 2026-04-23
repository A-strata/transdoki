"""
Тесты AJAX-поиска транспортных средств (vehicles:search → VehicleSearchView).

Endpoint возвращает единый JSON-контракт (transdoki/search.py):
    {"items": [...], "groups"?: [...], "hint"?: {...}}

Сценарии:
  - фильтр по type=truck / type=trailer,
  - own=1 (только ТС «наших» фирм),
  - carrier_id + группировка (аналогично PersonSearchView),
  - поиск по grn / brand,
  - tenant-изоляция.
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
        ids = [it["id"] for it in data["items"]]
        self.assertEqual(ids, [self.own_truck.pk])

    def test_own_carrier_with_query_two_groups(self):
        data = self._search(carrier_id=self.own_carrier.pk, q="0", type="truck")
        self.assertEqual([g["key"] for g in data["groups"]], ["carrier", "others"])

    def test_non_own_carrier_gives_flat_plus_hint(self):
        data = self._search(carrier_id=self.ext_carrier.pk)
        self.assertNotIn("groups", data)
        self.assertEqual(data["hint"]["type"], "warning")

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
