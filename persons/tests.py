"""
Тесты AJAX-поиска водителей (persons:search → PersonSearchView).

Endpoint возвращает единый JSON-контракт (transdoki/search.py):
    {"items": [...], "groups"?: [...], "hint"?: {...}}

Сценарии:
  - плоский ответ (без carrier_id),
  - хинт «не привязаны к перевозчику» при carrier_id=чужой/не-own,
  - группа carrier без заголовка при пустом q,
  - две группы carrier + «Другие» при непустом q,
  - поиск по surname / name / patronymic,
  - tenant-изоляция: чужих водителей не видно.
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import Account
from organizations.models import Organization
from persons.models import Person

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["*"])
class PersonSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="persearch", password="x")
        cls.account = Account.objects.create(name="Acc", owner=cls.user)
        cls.user.profile.account = cls.account
        cls.user.profile.save(update_fields=["account"])

        # Наш перевозчик — для него группировка работает.
        cls.own_carrier = Organization.objects.create(
            account=cls.account, full_name="ООО Мой Парк", short_name="МойПарк",
            inn="7707083893", is_own_company=True,
        )
        # Контрагент — с ним группировка не имеет смысла: carrier_id
        # должен дать flat+hint.
        cls.ext_carrier = Organization.objects.create(
            account=cls.account, full_name="ООО Клиент", short_name="Клиент",
            inn="7728168971", is_own_company=False,
        )

        # Два водителя «у нас», один — без работодателя (справочник).
        cls.own_driver = Person.objects.create(
            account=cls.account, name="Иван", surname="Иванов", patronymic="Иванович",
            phone="+79001112233", employer=cls.own_carrier,
        )
        cls.other_driver = Person.objects.create(
            account=cls.account, name="Пётр", surname="Петров", patronymic="Петрович",
            phone="+79002223344",
        )

    def setUp(self):
        self.c = Client()
        self.c.force_login(self.user)

    def _search(self, **params):
        url = reverse("persons:search")
        return self.c.get(url, params).json()

    def test_flat_response_without_carrier_id(self):
        data = self._search()
        ids = [it["id"] for it in data["items"]]
        self.assertIn(self.own_driver.pk, ids)
        self.assertIn(self.other_driver.pk, ids)
        self.assertNotIn("groups", data)
        self.assertNotIn("hint", data)

    def test_invalid_carrier_id_is_treated_as_missing(self):
        # Не-число → endpoint терпимо игнорирует.
        data = self._search(carrier_id="garbage")
        self.assertNotIn("groups", data)
        self.assertNotIn("hint", data)

    def test_non_own_carrier_gives_flat_plus_hint(self):
        data = self._search(carrier_id=self.ext_carrier.pk)
        self.assertNotIn("groups", data)
        self.assertEqual(data["hint"]["type"], "warning")
        self.assertIn("не привязаны", data["hint"]["text"].lower())

    def test_own_carrier_without_query_single_group_no_header(self):
        # carrier_id=own, q пуст → одна безымянная группа "carrier",
        # только водители этого перевозчика.
        data = self._search(carrier_id=self.own_carrier.pk)
        self.assertEqual(len(data["groups"]), 1)
        self.assertEqual(data["groups"][0]["key"], "carrier")
        self.assertIsNone(data["groups"][0]["label"])
        ids = [it["id"] for it in data["items"]]
        self.assertEqual(ids, [self.own_driver.pk])
        self.assertEqual(data["items"][0]["group"], "carrier")

    def test_own_carrier_with_query_two_groups(self):
        # q задан → показываем carrier + «Другие».
        data = self._search(carrier_id=self.own_carrier.pk, q="ов")
        group_keys = [g["key"] for g in data["groups"]]
        self.assertEqual(group_keys, ["carrier", "others"])
        self.assertEqual(data["groups"][1]["label"], "Другие")

        by_group = {"carrier": [], "others": []}
        for it in data["items"]:
            by_group[it["group"]].append(it["id"])
        self.assertEqual(by_group["carrier"], [self.own_driver.pk])
        self.assertIn(self.other_driver.pk, by_group["others"])

    def test_own_carrier_no_attached_drivers_falls_back_to_all_plus_hint(self):
        # Перевозчик без привязанных водителей: плоский ответ + hint.
        empty_carrier = Organization.objects.create(
            account=self.account, full_name="ООО Пусто", short_name="Пусто",
            inn="7736050003", is_own_company=True,
        )
        data = self._search(carrier_id=empty_carrier.pk)
        self.assertNotIn("groups", data)
        self.assertEqual(data["hint"]["type"], "warning")

    def test_search_is_and_across_words_or_across_fields(self):
        # "Иван Иванов" → должен найти И.И. Иванова по двум полям.
        data = self._search(q="Иван Иванов")
        ids = [it["id"] for it in data["items"]]
        self.assertEqual(ids, [self.own_driver.pk])

    def test_tenant_isolation(self):
        # Чужой account не должен видеть наших водителей.
        other_user = User.objects.create_user(username="other", password="x")
        other_account = Account.objects.create(name="Other", owner=other_user)
        other_user.profile.account = other_account
        other_user.profile.save(update_fields=["account"])

        c = Client()
        c.force_login(other_user)
        data = c.get(reverse("persons:search")).json()
        self.assertEqual(data["items"], [])
