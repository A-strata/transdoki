"""
Тесты переключателя области просмотра (scope toggle) на странице
списка рейсов.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Account, UserProfile
from organizations.models import Organization
from persons.models import Person
from trips.models import Trip
from vehicles.models import Vehicle

User = get_user_model()


class TripScopeSwitchTests(TestCase):
    """
    Фикстуры:
      - Аккаунт с ДВУМЯ собственными фирмами (own_a, own_b)
      - Внешний контрагент в том же аккаунте
      - По одному рейсу на каждую собственную фирму
      - Отдельный аккаунт + фирма + рейс — для проверки изоляции
    """

    @classmethod
    def setUpTestData(cls):
        # ── Основной аккаунт ──
        cls.user = User.objects.create_user(
            username="owner", password="pass12345",
            first_name="Иван", last_name="Иванов",
        )
        cls.account = Account.objects.create(name="Акк-1", owner=cls.user)
        cls.user.profile.account = cls.account
        cls.user.profile.role = UserProfile.Role.OWNER
        cls.user.profile.save()

        cls.own_a = Organization.objects.create(
            full_name='ООО "Альфа"', short_name="Альфа",
            inn="7707083893", is_own_company=True,
            created_by=cls.user, account=cls.account,
        )
        cls.own_b = Organization.objects.create(
            full_name='ООО "Бета"', short_name="Бета",
            inn="7702070139", is_own_company=True,
            created_by=cls.user, account=cls.account,
        )
        cls.external = Organization.objects.create(
            full_name="ИП Петров", short_name="ИП Петров",
            inn="7736050003",
            created_by=cls.user, account=cls.account,
        )

        cls.driver = Person.objects.create(
            name="Пётр", surname="Петров", patronymic="Петрович",
            phone="+79161234567",
            created_by=cls.user, account=cls.account,
        )
        cls.truck = Vehicle.objects.create(
            grn="А123ВС77", brand="МАЗ", vehicle_type="single",
            owner=cls.external,
            created_by=cls.user, account=cls.account,
        )

        cls.trip_a = Trip.objects.create(
            account=cls.account, created_by=cls.user,
            date_of_trip="2026-05-01",
            client=cls.own_a, carrier=cls.external,
            driver=cls.driver, truck=cls.truck, cargo="Груз A",
        )
        cls.trip_b = Trip.objects.create(
            account=cls.account, created_by=cls.user,
            date_of_trip="2026-05-02",
            client=cls.own_b, carrier=cls.external,
            driver=cls.driver, truck=cls.truck, cargo="Груз B",
        )

        # ── Другой аккаунт — для теста изоляции ──
        cls.other_user = User.objects.create_user(
            username="other", password="pass12345",
        )
        cls.other_account = Account.objects.create(
            name="Акк-чужой", owner=cls.other_user,
        )
        cls.other_user.profile.account = cls.other_account
        cls.other_user.profile.role = UserProfile.Role.OWNER
        cls.other_user.profile.save()

        cls.other_own = Organization.objects.create(
            full_name='ООО "Чужая"', short_name="Чужая",
            inn="1234567894", is_own_company=True,
            created_by=cls.other_user, account=cls.other_account,
        )
        cls.other_ext = Organization.objects.create(
            full_name="Контрагент Ч", short_name="Контрагент Ч",
            inn="9876543210",
            created_by=cls.other_user, account=cls.other_account,
        )
        cls.other_driver = Person.objects.create(
            name="Сидор", surname="Сидоров",
            phone="+79161112233",
            created_by=cls.other_user, account=cls.other_account,
        )
        cls.other_truck = Vehicle.objects.create(
            grn="Б456ГД77", brand="Volvo", vehicle_type="single",
            owner=cls.other_ext,
            created_by=cls.other_user, account=cls.other_account,
        )
        cls.other_trip = Trip.objects.create(
            account=cls.other_account, created_by=cls.other_user,
            date_of_trip="2026-05-03",
            client=cls.other_own, carrier=cls.other_ext,
            driver=cls.other_driver, truck=cls.other_truck,
            cargo="Груз чужой",
        )

    def setUp(self):
        self.client = Client(SERVER_NAME="localhost")
        self.client.force_login(self.user)

    def _list(self, **params):
        return self.client.get(reverse("trips:list"), params)

    def test_default_scope_is_own(self):
        """Без параметров — видим только рейсы current_org (== own_a)."""
        resp = self._list()
        self.assertEqual(resp.status_code, 200)
        trips = list(resp.context["trips"])
        self.assertIn(self.trip_a, trips)
        self.assertNotIn(self.trip_b, trips)
        self.assertFalse(resp.context["scope_all"])

    def test_scope_all_shows_trips_across_own_orgs(self):
        """?scope=all — видим рейсы ВСЕХ собственных фирм аккаунта."""
        resp = self._list(scope="all")
        self.assertEqual(resp.status_code, 200)
        trips = list(resp.context["trips"])
        self.assertIn(self.trip_a, trips)
        self.assertIn(self.trip_b, trips)
        self.assertTrue(resp.context["scope_all"])

    def test_scope_all_preserves_tenant_isolation(self):
        """scope=all не прорубает стену между аккаунтами."""
        resp = self._list(scope="all")
        trips = list(resp.context["trips"])
        self.assertNotIn(self.other_trip, trips)

    def test_scope_all_persists_in_session(self):
        """После ?scope=all следующий GET без параметра сохраняет режим."""
        self._list(scope="all")
        self.assertTrue(self.client.session.get("trips_scope_all"))

        resp = self._list()
        self.assertTrue(resp.context["scope_all"])
        self.assertIn(self.trip_b, list(resp.context["trips"]))

    def test_scope_own_clears_session(self):
        """?scope=own возвращает в дефолтный режим и перезаписывает сессию."""
        self._list(scope="all")
        self.assertTrue(self.client.session.get("trips_scope_all"))

        resp = self._list(scope="own")
        self.assertFalse(self.client.session.get("trips_scope_all"))
        self.assertFalse(resp.context["scope_all"])
        self.assertNotIn(self.trip_b, list(resp.context["trips"]))

    def test_invalid_scope_value_ignored(self):
        """?scope=bogus не должен ломать view или менять сессию."""
        resp = self._list(scope="bogus")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["scope_all"])
        self.assertFalse(self.client.session.get("trips_scope_all", False))

    def test_scope_switch_visible_when_two_own_orgs(self):
        resp = self._list()
        self.assertTrue(resp.context["scope_switch_visible"])
        self.assertEqual(resp.context["scope_own_orgs_count"], 2)

    def test_scope_switch_hidden_when_single_own_org(self):
        """При единственной own-фирме переключатель скрыт, all-режим недоступен."""
        # Превращаем own_b в обычного контрагента — так же снижает own_orgs count до 1
        # и не задевает trip_b (PROTECT не сработает).
        self.own_b.is_own_company = False
        self.own_b.save()

        resp = self._list(scope="all")
        self.assertFalse(resp.context["scope_switch_visible"])
        self.assertFalse(resp.context["scope_all"])
        self.assertEqual(resp.context["scope_own_orgs_count"], 1)

    def test_scope_all_url_in_query_string(self):
        """В scope=all query_string для пагинации содержит scope=all."""
        resp = self._list(scope="all")
        self.assertIn("scope=all", resp.context["query_string"])

    def test_scope_own_query_string_has_no_scope_param(self):
        """В scope=own query_string не содержит scope=own (дефолт не пишется)."""
        resp = self._list()
        self.assertNotIn("scope=", resp.context["query_string"])

    # ── Рендер HTML ──

    def test_rendered_switch_links_in_own_mode(self):
        """В own-режиме href 'own'-кнопки = ?page=1 (без scope), href 'all' = ?scope=all&page=1.
        Активный класс — на 'own'-кнопке."""
        resp = self.client.get(reverse("trips:list"))
        html = resp.content.decode("utf-8")
        # Ссылка на own — без scope-параметра.
        self.assertIn('href="?scope=own&amp;page=1"', html)
        # Ссылка на all — с scope=all.
        self.assertIn('href="?scope=all&amp;page=1"', html)
        # Активный класс стоит на own-кнопке (data-scope-target="own").
        self.assertIn('data-scope-target="own"', html)
        # Должна быть ровно одна .is-active в сегменте.
        # Грубая проверка: подсчитать вхождения "scope-tab is-active"
        # (обе кнопки всегда с "scope-tab", одна также с "is-active").
        active_count = html.count("scope-tab is-active")
        self.assertEqual(active_count, 1)

    def test_rendered_switch_links_in_all_mode(self):
        """В all-режиме активен 'all'; ссылки те же."""
        resp = self.client.get(reverse("trips:list"), {"scope": "all"})
        html = resp.content.decode("utf-8")
        # Обе ссылки присутствуют.
        self.assertIn('href="?scope=own&amp;page=1"', html)
        self.assertIn('href="?scope=all&amp;page=1"', html)
        # Конкретика фирм в title-подсказке кнопки «Все мои фирмы».
        self.assertIn("Сводный обзор по фирмам:", html)
        self.assertIn("Альфа", html)
        self.assertIn("Бета", html)
        # is-active ровно один.
        self.assertEqual(html.count("scope-tab is-active"), 1)
