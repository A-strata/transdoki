"""
Тесты AJAX-поиска водителей (persons:search → PersonSearchView).

Endpoint возвращает единый JSON-контракт (transdoki/search.py):
    {"items": [...], "groups"?: [...], "hint"?: {...}}

PersonSearchView работает в strict_carrier-режиме (как VehicleSearchView):
при наличии `carrier_id` выдача жёстко ограничивается водителями этого
перевозчика (employer_id == carrier.pk). Сценарий зеркальный с UX поля
«Автомобиль»: либо список водителей перевозчика, либо empty-state с
кнопкой «+ Добавить водителя» (quick-create подставит employer = carrier).

Сценарии:
  - плоский ответ (без carrier_id),
  - carrier_id (strict): свой/внешний перевозчик с водителями и без,
  - q без совпадений → пустой список без хинта (фронт нарисует empty-state),
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

        cls.own_carrier = Organization.objects.create(
            account=cls.account, full_name="ООО Мой Парк", short_name="МойПарк",
            inn="7707083893", is_own_company=True,
        )
        cls.ext_carrier = Organization.objects.create(
            account=cls.account, full_name="ООО Клиент", short_name="Клиент",
            inn="7728168971", is_own_company=False,
        )

        cls.own_driver = Person.objects.create(
            account=cls.account, name="Иван", surname="Иванов", patronymic="Иванович",
            phone="+79001112233", employer=cls.own_carrier,
        )
        cls.ext_driver = Person.objects.create(
            account=cls.account, name="Пётр", surname="Петров", patronymic="Петрович",
            phone="+79002223344", employer=cls.ext_carrier,
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
        self.assertIn(self.ext_driver.pk, ids)
        self.assertNotIn("groups", data)
        self.assertNotIn("hint", data)

    def test_invalid_carrier_id_is_treated_as_missing(self):
        # Не-число → endpoint терпимо игнорирует.
        data = self._search(carrier_id="garbage")
        self.assertNotIn("groups", data)
        self.assertNotIn("hint", data)

    def test_own_carrier_filtered_strictly_to_employees(self):
        # Strict-режим: дропдаун содержит ТОЛЬКО водителей выбранного
        # перевозчика. Никаких «Других», никаких фрилансеров.
        data = self._search(carrier_id=self.own_carrier.pk)
        self.assertEqual([g["key"] for g in data["groups"]], ["carrier"])
        self.assertIsNone(data["groups"][0]["label"])
        ids = [it["id"] for it in data["items"]]
        self.assertEqual(ids, [self.own_driver.pk])
        self.assertNotIn("hint", data)

    def test_external_carrier_filtered_strictly_to_employees(self):
        # «Наша фирма — заказчик», перевозчик внешний (is_own_company=False).
        # Поведение симметричное: только водители этого перевозчика.
        # Раньше здесь отдавался весь справочник + warning-хинт.
        data = self._search(carrier_id=self.ext_carrier.pk)
        self.assertEqual([g["key"] for g in data["groups"]], ["carrier"])
        ids = [it["id"] for it in data["items"]]
        self.assertEqual(ids, [self.ext_driver.pk])
        self.assertNotIn(self.own_driver.pk, ids)
        self.assertNotIn("hint", data)

    def test_own_carrier_with_query_only_carrier_group_no_others(self):
        # q="ов" матчит обоих водителей (Иванов и Петров), но в strict
        # дропдаун попадают только водители выбранного перевозчика.
        data = self._search(carrier_id=self.own_carrier.pk, q="ов")
        self.assertEqual([g["key"] for g in data["groups"]], ["carrier"])
        ids = [it["id"] for it in data["items"]]
        self.assertEqual(ids, [self.own_driver.pk])
        self.assertNotIn(self.ext_driver.pk, ids)

    def test_carrier_without_drivers_returns_empty_with_info_hint(self):
        # У перевозчика нет водителей и пользователь ничего не ищет —
        # пустой список + info-хинт. Фронт нарисует empty-state с
        # кнопкой «+ Добавить водителя» (quick-create подставит
        # employer = carrier).
        empty_carrier = Organization.objects.create(
            account=self.account, full_name="ООО Пусто", short_name="Пусто",
            inn="7736050003", is_own_company=True,
        )
        data = self._search(carrier_id=empty_carrier.pk)
        self.assertEqual(data["items"], [])
        self.assertNotIn("groups", data)
        self.assertEqual(data["hint"]["type"], "info")
        self.assertIn("Пусто", data["hint"]["text"])
        self.assertIn("ни одного водителя", data["hint"]["text"])

    def test_carrier_with_query_no_match_returns_empty_without_hint(self):
        # У перевозчика есть водитель, но q не совпадает — пустой список
        # БЕЗ хинта. Фронт нарисует обычный empty-state из ENTITY_DEFAULTS.
        data = self._search(carrier_id=self.own_carrier.pk, q="ZZZZZZZ")
        self.assertEqual(data["items"], [])
        self.assertNotIn("groups", data)
        self.assertNotIn("hint", data)

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
