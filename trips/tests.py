"""
Тесты мультиточечного маршрута (route builder).

Покрывают полный цикл взаимодействия фронтенда с бэкендом:
- GET-запросы: проверяют, что шаблон отдаёт правильные данные для JS
- POST-запросы: проверяют, что бэкенд корректно парсит points_json и создаёт/обновляет TripPoint
- Валидация: проверяют, что некорректные данные отклоняются с правильными ошибками
- Обратная совместимость: проверяют синхронизацию Trip.consignor / Trip.consignee
"""

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Account, UserProfile
from organizations.models import Organization
from persons.models import Person
from trips.models import Trip, TripPoint
from vehicles.models import Vehicle

User = get_user_model()


class RouteBuilderTestBase(TestCase):
    """
    Базовый класс с фикстурами для всех тестов маршрута.

    Создаёт минимальный набор данных, необходимый для создания рейса:
    - Account + User + UserProfile (tenant-изоляция)
    - 2 организации: «наша фирма» (is_own_company=True) и внешний контрагент
    - Водитель, привязанный к аккаунту
    - Грузовик, принадлежащий перевозчику (carrier)
    """

    @classmethod
    def setUpTestData(cls):
        # ── Аккаунт и пользователь ──
        cls.user = User.objects.create_user(
            username="testdriver", password="testpass123",
            first_name="Тест", last_name="Тестов",
        )
        cls.account = Account.objects.create(name="Тест-аккаунт", owner=cls.user)
        # Сигнал post_save на User автоматически создаёт пустой UserProfile —
        # обновляем его, а не создаём новый.
        cls.user.profile.account = cls.account
        cls.user.profile.role = UserProfile.Role.OWNER
        cls.user.profile.save()

        # ── Организации ──
        # ИНН должны проходить валидацию контрольной суммы (реальные публичные ИНН).
        # Наша фирма — будет заказчиком (client)
        cls.our_org = Organization.objects.create(
            full_name='ООО "Тест Транспорт"', short_name="Тест Транспорт",
            inn="7707083893", is_own_company=True,
            created_by=cls.user, account=cls.account,
        )
        # Внешний контрагент — будет перевозчиком (carrier)
        cls.external_org = Organization.objects.create(
            full_name="ИП Иванов", short_name="ИП Иванов",
            inn="7736050003",
            created_by=cls.user, account=cls.account,
        )
        # Третья организация — для тестов мультиточечности
        cls.third_org = Organization.objects.create(
            full_name='ООО "Склад"', short_name="Склад",
            inn="7702070139",
            created_by=cls.user, account=cls.account,
        )

        # ── Водитель ──
        cls.driver = Person.objects.create(
            name="Пётр", surname="Петров", patronymic="Петрович",
            phone="+79161234567",
            created_by=cls.user, account=cls.account,
        )

        # ── Транспорт (принадлежит перевозчику) ──
        cls.truck = Vehicle.objects.create(
            grn="А123ВС77", brand="МАЗ", vehicle_type="single",
            owner=cls.external_org,
            created_by=cls.user, account=cls.account,
        )

    def setUp(self):
        """Авторизуем пользователя перед каждым тестом."""
        self.client = Client(SERVER_NAME="localhost")
        self.client.force_login(self.user)

    # ── Хелперы ──

    def _base_trip_data(self, **overrides):
        """
        Возвращает минимальный набор полей Trip для POST-запроса.
        Все обязательные поля заполнены валидными значениями.
        overrides позволяет переопределить любое поле.
        """
        data = {
            "date_of_trip": "2026-05-01",
            "client": str(self.our_org.pk),
            "carrier": str(self.external_org.pk),
            "driver": str(self.driver.pk),
            "truck": str(self.truck.pk),
            "cargo": "Стройматериалы",
        }
        data.update(overrides)
        return data

    def _make_point(self, point_type="LOAD", address="Москва, ул. Тестовая 1",
                    planned_date="2026-05-01", planned_time="08:00",
                    organization="", **kwargs):
        """
        Создаёт dict одной точки маршрута для JSON.
        Поведение по умолчанию — валидная точка с обязательными полями.
        """
        point = {
            "point_type": point_type,
            "address": address,
            "planned_date": planned_date,
            "planned_time": planned_time,
            "organization": str(organization) if organization else "",
            "loading_type": "",
            "contact_name": "",
            "contact_phone": "",
        }
        point.update(kwargs)
        return point

    def _post_with_points(self, points, url=None, **trip_overrides):
        """
        Отправляет POST с указанными точками маршрута.
        Упрощает типичный сценарий: собрать данные Trip + points_json → POST.
        """
        if url is None:
            url = reverse("trips:create")
        data = self._base_trip_data(**trip_overrides)
        data["points_json"] = json.dumps(points)
        return self.client.post(url, data)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. GET-запросы: проверяем, что шаблон отдаёт нужные данные для JS
# ═══════════════════════════════════════════════════════════════════════════════

class RouteBuilderGetTests(RouteBuilderTestBase):
    """Тесты GET-запросов — шаблон отдаёт конфигурацию для route builder JS."""

    def test_create_page_contains_route_builder_elements(self):
        """
        GET /trips/create/ должен содержать:
        - div#route-builder (контейнер, который JS заполняет карточками точек)
        - div#route-config с data-points (начальные данные для JS)
        - input[name=points_json] (hidden input, куда JS запишет данные при submit)
        """
        resp = self.client.get(reverse("trips:create"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('id="route-builder"', content)
        self.assertIn('id="route-config"', content)
        self.assertIn('name="points_json"', content)

    def test_create_page_default_points(self):
        """
        Для новой формы бэкенд должен передать 2 дефолтные точки:
        1 LOAD + 1 UNLOAD — минимальный маршрут, с которого пользователь начинает.
        JS прочитает data-points и отрендерит 2 свёрнутые карточки.
        """
        resp = self.client.get(reverse("trips:create"))
        content = resp.content.decode()
        # Извлекаем JSON из data-points
        import re
        match = re.search(r'data-points="([^"]*)"', content)
        self.assertIsNotNone(match, "data-points атрибут не найден в HTML")
        # HTML-entities декодирование
        import html
        points = json.loads(html.unescape(match.group(1)))
        self.assertEqual(len(points), 2, "Должно быть ровно 2 дефолтные точки")
        self.assertEqual(points[0]["point_type"], "LOAD")
        self.assertEqual(points[1]["point_type"], "UNLOAD")

    def test_create_page_has_org_search_url(self):
        """
        Route builder нуждается в URL для AJAX-поиска организаций.
        Проверяем, что data-org-search-url присутствует и ведёт на правильный endpoint.
        """
        resp = self.client.get(reverse("trips:create"))
        content = resp.content.decode()
        self.assertIn('data-org-search-url=', content)
        self.assertIn(reverse("organizations:search"), content)

    def test_create_page_has_address_suggest_url(self):
        """
        Route builder нуждается в URL для подсказок адресов (DaData).
        Проверяем, что data-address-suggest-url присутствует.
        """
        resp = self.client.get(reverse("trips:create"))
        content = resp.content.decode()
        self.assertIn('data-address-suggest-url=', content)

    def test_edit_page_loads_existing_points(self):
        """
        GET /trips/<pk>/edit/ должен передать в data-points
        реальные данные точек из БД — чтобы JS отрендерил карточки
        с уже заполненными адресами, датами и организациями.
        """
        # Сначала создаём рейс с точками
        points = [
            self._make_point("LOAD", "Москва, Складская 5", organization=self.our_org.pk),
            self._make_point("UNLOAD", "СПб, Невский 1", organization=self.third_org.pk),
        ]
        resp = self._post_with_points(points)
        self.assertEqual(resp.status_code, 302, "Рейс должен быть создан")
        trip = Trip.objects.order_by("-pk").first()

        # Теперь открываем форму редактирования
        resp = self.client.get(reverse("trips:edit", kwargs={"pk": trip.pk}))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()

        # Проверяем, что адреса из БД попали в data-points
        self.assertIn("Москва, Складская 5", content)
        self.assertIn("СПб, Невский 1", content)

    def test_copy_from_loads_source_points(self):
        """
        GET /trips/create/?copy_from=<pk> должен скопировать точки из исходного рейса.
        Это позволяет пользователю быстро создать похожий рейс.
        """
        # Создаём исходный рейс
        points = [
            self._make_point("LOAD", "Копия-адрес-погрузки"),
            self._make_point("UNLOAD", "Копия-адрес-выгрузки"),
        ]
        resp = self._post_with_points(points)
        source_trip = Trip.objects.order_by("-pk").first()

        # Открываем форму с copy_from
        resp = self.client.get(reverse("trips:create") + f"?copy_from={source_trip.pk}")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn("Копия-адрес-погрузки", content)
        self.assertIn("Копия-адрес-выгрузки", content)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. POST-запросы: создание рейса с точками
# ═══════════════════════════════════════════════════════════════════════════════

class RouteBuilderCreateTests(RouteBuilderTestBase):
    """Тесты POST /trips/create/ — бэкенд парсит points_json и создаёт TripPoint."""

    def test_create_minimal_route(self):
        """
        Минимальный маршрут: 1 LOAD + 1 UNLOAD.
        Бэкенд должен создать Trip + 2 TripPoint с sequence 1 и 2.
        """
        points = [
            self._make_point("LOAD", "Москва"),
            self._make_point("UNLOAD", "СПб"),
        ]
        resp = self._post_with_points(points)

        # POST успешен → редирект на страницу деталей
        self.assertEqual(resp.status_code, 302)

        trip = Trip.objects.order_by("-pk").first()
        self.assertIsNotNone(trip)

        db_points = list(trip.points.order_by("sequence"))
        self.assertEqual(len(db_points), 2)

        # Проверяем первую точку (погрузка)
        self.assertEqual(db_points[0].point_type, "LOAD")
        self.assertEqual(db_points[0].sequence, 1)
        self.assertEqual(db_points[0].address, "Москва")

        # Проверяем вторую точку (выгрузка)
        self.assertEqual(db_points[1].point_type, "UNLOAD")
        self.assertEqual(db_points[1].sequence, 2)
        self.assertEqual(db_points[1].address, "СПб")

    def test_create_multipoint_route(self):
        """
        Мультиточечный маршрут: 2 LOAD + 1 UNLOAD.
        Например: забрать груз на двух складах, выгрузить в одном месте.
        Sequence должен быть 1, 2, 3 — по порядку массива, не по типу.
        """
        points = [
            self._make_point("LOAD", "Склад-1"),
            self._make_point("LOAD", "Склад-2", planned_date="2026-05-01", planned_time="10:00"),
            self._make_point("UNLOAD", "Выгрузка"),
        ]
        resp = self._post_with_points(points)
        self.assertEqual(resp.status_code, 302)

        trip = Trip.objects.order_by("-pk").first()
        db_points = list(trip.points.order_by("sequence"))
        self.assertEqual(len(db_points), 3)
        self.assertEqual(db_points[0].address, "Склад-1")
        self.assertEqual(db_points[0].sequence, 1)
        self.assertEqual(db_points[1].address, "Склад-2")
        self.assertEqual(db_points[1].sequence, 2)
        self.assertEqual(db_points[2].address, "Выгрузка")
        self.assertEqual(db_points[2].sequence, 3)

    def test_create_with_all_point_fields(self):
        """
        Проверяем, что ВСЕ поля точки маршрута сохраняются корректно:
        point_type, address, planned_date, organization, loading_type, contact_name, contact_phone.
        """
        points = [
            self._make_point(
                "LOAD", "Москва, ул. Складская 12",
                planned_date="2026-05-02", planned_time="09:30",
                organization=self.our_org.pk,
                loading_type="rear",
                contact_name="Иванов И.И.",
                contact_phone="79161234567",
            ),
            self._make_point("UNLOAD", "СПб, Софийская 44"),
        ]
        resp = self._post_with_points(points)
        self.assertEqual(resp.status_code, 302)

        trip = Trip.objects.order_by("-pk").first()
        load_point = trip.points.get(sequence=1)
        self.assertEqual(load_point.point_type, "LOAD")
        self.assertEqual(load_point.address, "Москва, ул. Складская 12")
        self.assertEqual(load_point.organization_id, self.our_org.pk)
        self.assertEqual(load_point.loading_type, "rear")
        self.assertEqual(load_point.contact_name, "Иванов И.И.")
        self.assertEqual(load_point.contact_phone, "79161234567")

    def test_create_with_organization_null(self):
        """
        Организация на точке — необязательное поле.
        Пустая строка в JSON должна сохраниться как NULL в БД.
        """
        points = [
            self._make_point("LOAD", "Адрес-1", organization=""),
            self._make_point("UNLOAD", "Адрес-2", organization=""),
        ]
        resp = self._post_with_points(points)
        self.assertEqual(resp.status_code, 302)

        trip = Trip.objects.order_by("-pk").first()
        for pt in trip.points.all():
            self.assertIsNone(pt.organization_id, "organization должен быть NULL при пустом значении")

    def test_redirect_to_detail_page(self):
        """
        После успешного создания рейса пользователь перенаправляется
        на страницу деталей созданного рейса.
        """
        points = [
            self._make_point("LOAD", "А"),
            self._make_point("UNLOAD", "Б"),
        ]
        resp = self._post_with_points(points)
        self.assertEqual(resp.status_code, 302)
        trip = Trip.objects.order_by("-pk").first()
        expected_url = reverse("trips:detail", kwargs={"pk": trip.pk})
        self.assertEqual(resp.url, expected_url)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. POST-запросы: обновление рейса с точками
# ═══════════════════════════════════════════════════════════════════════════════

class RouteBuilderUpdateTests(RouteBuilderTestBase):
    """Тесты POST /trips/<pk>/edit/ — обновление точек маршрута."""

    def _create_trip_with_points(self, points):
        """Хелпер: создаёт рейс и возвращает его из БД."""
        resp = self._post_with_points(points)
        self.assertEqual(resp.status_code, 302)
        return Trip.objects.order_by("-pk").first()

    def test_update_replaces_points(self):
        """
        При обновлении рейса старые точки удаляются и создаются новые.
        Это позволяет менять количество, тип и порядок точек.
        """
        # Создаём с 2 точками
        trip = self._create_trip_with_points([
            self._make_point("LOAD", "Старый-адрес-1"),
            self._make_point("UNLOAD", "Старый-адрес-2"),
        ])
        old_point_ids = set(trip.points.values_list("pk", flat=True))

        # Обновляем на 3 точки с новыми адресами
        new_points = [
            self._make_point("LOAD", "Новый-адрес-1"),
            self._make_point("LOAD", "Новый-адрес-2", planned_date="2026-05-01", planned_time="10:00"),
            self._make_point("UNLOAD", "Новый-адрес-3"),
        ]
        resp = self._post_with_points(
            new_points,
            url=reverse("trips:edit", kwargs={"pk": trip.pk}),
        )
        self.assertEqual(resp.status_code, 302)

        trip.refresh_from_db()
        db_points = list(trip.points.order_by("sequence"))

        # Старых точек больше нет
        self.assertEqual(len(db_points), 3)
        new_point_ids = {p.pk for p in db_points}
        self.assertTrue(old_point_ids.isdisjoint(new_point_ids),
                        "Старые точки должны быть удалены, новые — созданы заново")

        # Новые данные на месте
        self.assertEqual(db_points[0].address, "Новый-адрес-1")
        self.assertEqual(db_points[1].address, "Новый-адрес-2")
        self.assertEqual(db_points[2].address, "Новый-адрес-3")

    def test_update_reorder_points(self):
        """
        Пользователь может поменять порядок точек кнопками ↑↓.
        JS отправляет массив в новом порядке — бэкенд сохраняет sequence по индексу.
        """
        trip = self._create_trip_with_points([
            self._make_point("LOAD", "Первый"),
            self._make_point("UNLOAD", "Второй"),
        ])

        # Меняем порядок: UNLOAD первый, LOAD второй
        reordered = [
            self._make_point("UNLOAD", "Второй"),
            self._make_point("LOAD", "Первый"),
        ]
        resp = self._post_with_points(
            reordered,
            url=reverse("trips:edit", kwargs={"pk": trip.pk}),
        )
        self.assertEqual(resp.status_code, 302)

        trip.refresh_from_db()
        db_points = list(trip.points.order_by("sequence"))
        self.assertEqual(db_points[0].point_type, "UNLOAD")
        self.assertEqual(db_points[0].sequence, 1)
        self.assertEqual(db_points[1].point_type, "LOAD")
        self.assertEqual(db_points[1].sequence, 2)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Валидация: отклонение некорректных данных
# ═══════════════════════════════════════════════════════════════════════════════

class RouteBuilderValidationTests(RouteBuilderTestBase):
    """
    Тесты серверной валидации точек маршрута.

    Фронтенд тоже валидирует, но бэкенд — последний рубеж.
    Здесь проверяем, что невалидные данные не проходят даже если JS обошли.
    """

    def test_empty_points_json_rejected(self):
        """
        Пустой массив точек — невалиден.
        Бэкенд должен вернуть 200 (форма с ошибками), а не 302 (успех).
        """
        resp = self._post_with_points([])
        self.assertEqual(resp.status_code, 200, "Пустой маршрут не должен сохраняться")
        # Trip не должен быть создан
        self.assertEqual(Trip.objects.count(), 0)

    def test_missing_points_json_rejected(self):
        """
        Если JS не отправил points_json (сломанный клиент) —
        бэкенд должен обработать это gracefully, не упасть с 500.
        """
        data = self._base_trip_data()
        # Намеренно не добавляем points_json
        resp = self.client.post(reverse("trips:create"), data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Trip.objects.count(), 0)

    def test_only_load_without_unload_rejected(self):
        """
        Маршрут только из LOAD-точек (без UNLOAD) не имеет смысла.
        Груз должен куда-то приехать.
        """
        points = [
            self._make_point("LOAD", "Склад-1"),
            self._make_point("LOAD", "Склад-2", planned_date="2026-05-01", planned_time="10:00"),
        ]
        resp = self._post_with_points(points)
        self.assertEqual(resp.status_code, 200, "Маршрут без UNLOAD не должен сохраняться")
        self.assertEqual(Trip.objects.count(), 0)

    def test_only_unload_without_load_rejected(self):
        """
        Маршрут только из UNLOAD-точек (без LOAD) тоже невалиден.
        Нужно откуда-то забрать груз.
        """
        points = [
            self._make_point("UNLOAD", "Склад-1"),
            self._make_point("UNLOAD", "Склад-2", planned_date="2026-05-01", planned_time="10:00"),
        ]
        resp = self._post_with_points(points)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Trip.objects.count(), 0)

    def test_point_without_address_rejected(self):
        """
        Адрес — обязательное поле каждой точки.
        TripPointForm.address.required=True → ошибка валидации.
        """
        points = [
            self._make_point("LOAD", address=""),  # пустой адрес
            self._make_point("UNLOAD", "СПб"),
        ]
        resp = self._post_with_points(points)
        self.assertEqual(resp.status_code, 200, "Точка без адреса не должна сохраняться")
        self.assertEqual(Trip.objects.count(), 0)

    def test_point_without_planned_date_rejected(self):
        """
        Дата и время — обязательное поле каждой точки.
        Пустая дата → ошибка валидации.
        """
        points = [
            self._make_point("LOAD", "Москва", planned_date=""),  # пустая дата
            self._make_point("UNLOAD", "СПб"),
        ]
        resp = self._post_with_points(points)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Trip.objects.count(), 0)

    def test_invalid_json_handled_gracefully(self):
        """
        Сломанный JSON в points_json (атака или баг) не должен вызывать 500.
        Бэкенд парсит через json.loads() в try/except и возвращает форму с ошибками.
        """
        data = self._base_trip_data()
        data["points_json"] = "{broken json[["
        resp = self.client.post(reverse("trips:create"), data)
        self.assertIn(resp.status_code, [200, 400],
                      "Сломанный JSON не должен вызывать 500")
        self.assertEqual(Trip.objects.count(), 0)

    def test_contact_name_without_phone_rejected(self):
        """
        Если указано имя контакта, но не указан телефон — ошибка.
        Правило: оба поля заполняются вместе или оба пустые.
        """
        points = [
            self._make_point("LOAD", "Москва", contact_name="Иванов", contact_phone=""),
            self._make_point("UNLOAD", "СПб"),
        ]
        resp = self._post_with_points(points)
        self.assertEqual(resp.status_code, 200, "Имя без телефона не должно пройти валидацию")
        self.assertEqual(Trip.objects.count(), 0)

    def test_validation_errors_returned_in_points_json(self):
        """
        При ошибках валидации бэкенд должен вернуть points_json обратно в шаблон,
        чтобы JS отрисовал карточки с теми данными, что пользователь ввёл,
        а не сбросил форму в начальное состояние.
        """
        points = [
            self._make_point("LOAD", "Москва", planned_date=""),  # невалидная точка
            self._make_point("UNLOAD", "СПб"),
        ]
        resp = self._post_with_points(points)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        # Данные точек должны вернуться в шаблон
        self.assertIn("Москва", content, "Адрес из невалидных данных должен вернуться в шаблон")
        self.assertIn("СПб", content)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Изоляция по аккаунту (tenant safety)
# ═══════════════════════════════════════════════════════════════════════════════

class RouteBuilderTenantIsolationTests(RouteBuilderTestBase):
    """
    Тесты изоляции данных между аккаунтами.

    Каждый аккаунт видит только свои рейсы.
    Попытка редактировать чужой рейс должна вернуть 404.
    """

    def test_cannot_edit_trip_from_another_account(self):
        """
        Пользователь не может открыть форму редактирования чужого рейса.
        View фильтрует queryset по account — чужой рейс не найдётся → 404.
        """
        # Создаём рейс от текущего пользователя
        points = [
            self._make_point("LOAD", "А"),
            self._make_point("UNLOAD", "Б"),
        ]
        resp = self._post_with_points(points)
        trip = Trip.objects.order_by("-pk").first()

        # Создаём другого пользователя с другим аккаунтом
        other_user = User.objects.create_user(username="other", password="pass123")
        other_account = Account.objects.create(name="Другой аккаунт", owner=other_user)
        other_user.profile.account = other_account
        other_user.profile.role = UserProfile.Role.OWNER
        other_user.profile.save()

        # Логинимся как другой пользователь
        self.client.force_login(other_user)

        # Пытаемся открыть чужой рейс
        resp = self.client.get(reverse("trips:edit", kwargs={"pk": trip.pk}))
        self.assertEqual(resp.status_code, 404,
                         "Чужой рейс не должен быть доступен для редактирования")

    def test_cannot_use_org_from_another_account(self):
        """
        В points_json передан ID организации из чужого аккаунта.

        clean_organization() в TripPointForm проверяет, что организация
        принадлежит аккаунту пользователя через _validation_qs.
        Чужая организация → ошибка валидации → рейс не создаётся (200),
        либо создаётся, но без привязки чужой организации.
        """
        # Создаём организацию в другом аккаунте
        other_user = User.objects.create_user(username="other2", password="pass123")
        other_account = Account.objects.create(name="Чужой", owner=other_user)
        other_user.profile.account = other_account
        other_user.profile.role = UserProfile.Role.OWNER
        other_user.profile.save()
        foreign_org = Organization.objects.create(
            full_name="Чужая ООО", short_name="Чужая",
            inn="7740000076",
            created_by=other_user, account=other_account,
        )

        # Пытаемся использовать чужую организацию в своём рейсе
        points = [
            self._make_point("LOAD", "Москва", organization=foreign_org.pk),
            self._make_point("UNLOAD", "СПб"),
        ]
        resp = self._post_with_points(points)

        if resp.status_code == 302:
            # Рейс создан — проверяем что чужая организация НЕ привязалась
            trip = Trip.objects.filter(account=self.account).order_by("-pk").first()
            for pt in trip.points.all():
                self.assertNotEqual(
                    pt.organization_id, foreign_org.pk,
                    "Чужая организация не должна привязаться к точке маршрута",
                )
        else:
            # Форма вернулась с ошибкой — рейс не создан, это тоже ок
            self.assertEqual(resp.status_code, 200)
