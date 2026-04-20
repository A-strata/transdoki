from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from accounts.middleware import CurrentOrganizationMiddleware
from accounts.models import Account, UserProfile
from organizations.models import Organization

User = get_user_model()


class CurrentOrganizationMiddlewareTests(TestCase):
    """Fallback-цепочка: session → profile.last_active_org → own_orgs[0]."""

    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(name="Acc")
        cls.user = User.objects.create_user(username="u1", password="x")
        profile = cls.user.profile
        profile.account = cls.account
        profile.save(update_fields=["account"])

        # Порядок создания: A раньше B раньше C.
        cls.org_a = Organization.objects.create(
            account=cls.account,
            full_name="A LLC",
            short_name="A",
            inn="7707083893",
            is_own_company=True,
        )
        cls.org_b = Organization.objects.create(
            account=cls.account,
            full_name="B LLC",
            short_name="B",
            inn="7728168971",
            is_own_company=True,
        )
        cls.org_c = Organization.objects.create(
            account=cls.account,
            full_name="C LLC",
            short_name="C",
            inn="5003052454",
            is_own_company=True,
        )

    def _run(self, session_data=None, last_active_org=None):
        if last_active_org is not None:
            profile = UserProfile.objects.get(user=self.user)
            profile.last_active_org = last_active_org
            profile.save(update_fields=["last_active_org"])

        user = User.objects.select_related("profile").get(pk=self.user.pk)
        request = RequestFactory().get("/")
        request.user = user

        class _Session(dict):
            modified = False
            session_key = None

        request.session = _Session(session_data or {})

        mw = CurrentOrganizationMiddleware(lambda r: HttpResponse())
        mw(request)
        return request

    def test_own_orgs_ordered_by_creation(self):
        request = self._run()
        self.assertEqual(
            [o.pk for o in request.own_orgs],
            [self.org_a.pk, self.org_b.pk, self.org_c.pk],
        )

    def test_session_hit_wins(self):
        request = self._run(
            session_data={"current_org_id": self.org_c.pk},
            last_active_org=self.org_b,
        )
        self.assertEqual(request.current_org, self.org_c)

    def test_profile_fallback_when_no_session(self):
        request = self._run(last_active_org=self.org_b)
        self.assertEqual(request.current_org, self.org_b)
        self.assertEqual(request.session["current_org_id"], self.org_b.pk)

    def test_cold_start_picks_oldest(self):
        request = self._run()
        self.assertEqual(request.current_org, self.org_a)
        self.assertEqual(request.session["current_org_id"], self.org_a.pk)

    def test_stale_session_id_falls_through_to_profile(self):
        request = self._run(
            session_data={"current_org_id": 999999},
            last_active_org=self.org_b,
        )
        self.assertEqual(request.current_org, self.org_b)

    def test_profile_last_active_from_foreign_account_is_ignored_and_cleared(self):
        """
        Если last_active_org указывает на организацию ЧУЖОГО account
        (например, после перемещения пользователя), middleware не должен
        её выбирать и должен очистить stale id.
        """
        other_account = Account.objects.create(name="Other")
        foreign_org = Organization.objects.create(
            account=other_account,
            full_name="Foreign LLC",
            short_name="F",
            inn="6449013711",
            is_own_company=True,
        )
        profile = UserProfile.objects.get(user=self.user)
        profile.last_active_org = foreign_org
        profile.save(update_fields=["last_active_org"])

        request = self._run()

        self.assertEqual(request.current_org, self.org_a)
        profile.refresh_from_db()
        self.assertIsNone(profile.last_active_org_id)

    def test_no_own_orgs(self):
        Organization.objects.filter(account=self.account).delete()
        request = self._run()
        self.assertEqual(request.own_orgs, [])
        self.assertIsNone(request.current_org)


class LastActiveOrgSetNullTests(TestCase):
    """Удаление организации должно очистить profile.last_active_org."""

    def test_set_null_on_delete(self):
        account = Account.objects.create(name="Acc2")
        user = User.objects.create_user(username="u2", password="x")
        profile = user.profile
        profile.account = account
        profile.save(update_fields=["account"])

        org = Organization.objects.create(
            account=account,
            full_name="X LLC",
            short_name="X",
            inn="7707083893",
            is_own_company=True,
        )
        profile.last_active_org = org
        profile.save(update_fields=["last_active_org"])

        org.delete()
        profile.refresh_from_db()
        self.assertIsNone(profile.last_active_org_id)


@override_settings(ALLOWED_HOSTS=["*"])
class CabinetPageRenderTests(TestCase):
    """
    Smoke-тест /accounts/cabinet/: страница отдаёт 200 и шаблоны парсятся.
    Покрывает ошибки вроде незакрытых {% block %}/{% comment %} в cabinet.html
    и partial-файлах, которые unit-тесты view не ловят.
    """

    def test_cabinet_renders_for_owner(self):
        user = User.objects.create_user(username="owner-cab", password="x")
        account = Account.objects.create(name="A", owner=user)
        profile = user.profile
        profile.account = account
        profile.role = UserProfile.Role.OWNER
        profile.save(update_fields=["account", "role"])

        client = Client()
        client.force_login(user)
        resp = client.get(reverse("accounts:cabinet"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        # Ключевые куски UI v1.3 — self-row первой строкой, 5 модалок,
        # toast-контейнер создаётся динамически (в партиале его нет).
        self.assertIn("lk-team-list", content)
        self.assertIn("lk-team-row is-self", content)
        self.assertIn("invite-modal", content)
        self.assertIn("edit-self-modal", content)
        self.assertIn("edit-user-modal", content)
        self.assertIn("reset-confirm-modal", content)
        self.assertIn("reset-success-modal", content)
        # Регресс: {# ... #} однострочный, если его писать на несколько
        # строк — парсер Django не распознаёт и тело утекает в HTML.
        # Ловим утечку по маркеру «{#» или «#}» в итоговом ответе.
        self.assertNotIn("{#", content)
        self.assertNotIn("#}", content)

    def test_cabinet_renders_for_dispatcher(self):
        owner = User.objects.create_user(username="own2", password="x")
        account = Account.objects.create(name="B", owner=owner)
        owner.profile.account = account
        owner.profile.role = UserProfile.Role.OWNER
        owner.profile.save(update_fields=["account", "role"])

        disp = User.objects.create_user(username="disp-cab", password="x")
        disp.profile.account = account
        disp.profile.role = UserProfile.Role.DISPATCHER
        disp.profile.save(update_fields=["account", "role"])

        client = Client()
        client.force_login(disp)
        resp = client.get(reverse("accounts:cabinet"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        # Для диспетчера self-row всё равно рендерится (может править своё ФИО
        # через edit-self-modal), но kebab у чужих строк не виден.
        self.assertIn("lk-team-row is-self", content)
        self.assertIn("edit-self-modal", content)
        # Кнопка «+ Пригласить» скрыта (can_manage_users=False).
        self.assertNotIn("data-lk-modal-open=\"invite-modal\"", content)


@override_settings(ALLOWED_HOSTS=["*"])
class AccountUserUpdateViewPermissionTests(TestCase):
    """
    Матрица прав AccountUserUpdateView (см. ТЗ редизайна «Профиль и команда»
    §4). Гейт прав разнесён: self-профиль редактируется любой ролью (только
    ФИО), чужой — только owner/admin. Тесты — регрессионный щит.
    """

    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(name="Team")

        # Владелец
        cls.owner_user = User.objects.create_user(username="owner@x", password="x")
        cls.owner_profile = cls.owner_user.profile
        cls.owner_profile.account = cls.account
        cls.owner_profile.role = UserProfile.Role.OWNER
        cls.owner_profile.save(update_fields=["account", "role"])

        # Админ
        cls.admin_user = User.objects.create_user(username="admin@x", password="x")
        cls.admin_profile = cls.admin_user.profile
        cls.admin_profile.account = cls.account
        cls.admin_profile.role = UserProfile.Role.ADMIN
        cls.admin_profile.save(update_fields=["account", "role"])

        # Диспетчер (любой profile, которому по ТЗ всё равно должен
        # быть доступен self-ФИО).
        cls.dispatcher_user = User.objects.create_user(username="disp@x", password="x")
        cls.dispatcher_profile = cls.dispatcher_user.profile
        cls.dispatcher_profile.account = cls.account
        cls.dispatcher_profile.role = UserProfile.Role.DISPATCHER
        cls.dispatcher_profile.save(update_fields=["account", "role"])

        # Логист — цель для изменений от админа
        cls.logist_user = User.objects.create_user(username="log@x", password="x")
        cls.logist_profile = cls.logist_user.profile
        cls.logist_profile.account = cls.account
        cls.logist_profile.role = UserProfile.Role.LOGIST
        cls.logist_profile.save(update_fields=["account", "role"])

    def _post(self, actor, target_profile_id, data):
        client = Client()
        client.force_login(actor)
        return client.post(
            reverse("accounts:user_update", args=[target_profile_id]),
            data=data,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_dispatcher_can_update_own_name_but_not_role(self):
        resp = self._post(
            self.dispatcher_user,
            self.dispatcher_profile.pk,
            {"first_name": "Ivan", "last_name": "Test", "role": UserProfile.Role.ADMIN},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["first_name"], "Ivan")
        self.assertEqual(body["last_name"], "Test")

        self.dispatcher_profile.refresh_from_db()
        self.dispatcher_user.refresh_from_db()
        self.assertEqual(self.dispatcher_user.first_name, "Ivan")
        self.assertEqual(self.dispatcher_user.last_name, "Test")
        # Попытка повысить себя до admin — проигнорирована.
        self.assertEqual(self.dispatcher_profile.role, UserProfile.Role.DISPATCHER)

    def test_dispatcher_cannot_update_others(self):
        resp = self._post(
            self.dispatcher_user,
            self.logist_profile.pk,
            {"first_name": "Hack", "last_name": "Hack", "role": UserProfile.Role.ADMIN},
        )
        self.assertEqual(resp.status_code, 403)
        body = resp.json()
        self.assertFalse(body["ok"])

        self.logist_profile.refresh_from_db()
        self.logist_user.refresh_from_db()
        # Ни ФИО, ни роль не изменились.
        self.assertEqual(self.logist_user.first_name, "")
        self.assertEqual(self.logist_profile.role, UserProfile.Role.LOGIST)

    def test_admin_updates_first_name_and_role_in_one_post(self):
        """
        v1.3 фича: `#edit-user-modal` объединяет ФИО и роль — один POST
        на user_update обновляет оба поля и возвращает новый role_display.
        Бэкенд уже принимает оба, тест фиксирует ожидание для клиента.
        """
        resp = self._post(
            self.admin_user,
            self.logist_profile.pk,
            {
                "first_name": "Pavel",
                "last_name": "Ivanov",
                "role": UserProfile.Role.DISPATCHER,
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["first_name"], "Pavel")
        self.assertEqual(body["last_name"], "Ivanov")
        # role_display отдаётся в локализованной форме — клиентский JS
        # показывает её в мета-строке команды.
        self.assertEqual(body["role_display"], "Диспетчер")

        self.logist_profile.refresh_from_db()
        self.logist_user.refresh_from_db()
        self.assertEqual(self.logist_user.first_name, "Pavel")
        self.assertEqual(self.logist_profile.role, UserProfile.Role.DISPATCHER)

    def test_admin_can_reset_target_password_twice(self):
        """
        Регресс: после первого POST /reset-password/ бэкенд не должен
        блокировать повторный вызов для той же цели. UI-баг «кнопка
        сброса работает только один раз» не должен повторяться на backend.
        """
        client = Client()
        client.force_login(self.admin_user)
        url = reverse("accounts:user_reset_password", args=[self.logist_profile.pk])

        resp1 = client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp1.status_code, 200)
        self.assertTrue(resp1.json()["ok"])
        pw1 = resp1.json()["temp_password"]

        resp2 = client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.json()["ok"])
        pw2 = resp2.json()["temp_password"]

        # Два разных временных пароля (генератор случайный).
        self.assertNotEqual(pw1, pw2)

    def test_admin_can_update_others_but_not_owner(self):
        # Админ правит логиста — ok, роль и ФИО меняются.
        resp = self._post(
            self.admin_user,
            self.logist_profile.pk,
            {
                "first_name": "Pavel",
                "last_name": "Ivanov",
                "role": UserProfile.Role.DISPATCHER,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.logist_profile.refresh_from_db()
        self.logist_user.refresh_from_db()
        self.assertEqual(self.logist_user.first_name, "Pavel")
        self.assertEqual(self.logist_profile.role, UserProfile.Role.DISPATCHER)

        # Админ пытается править владельца — 400, владелец неизменен.
        resp = self._post(
            self.admin_user,
            self.owner_profile.pk,
            {
                "first_name": "Ghost",
                "last_name": "Ghost",
                "role": UserProfile.Role.DISPATCHER,
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.owner_profile.refresh_from_db()
        self.owner_user.refresh_from_db()
        self.assertEqual(self.owner_user.first_name, "")
        self.assertEqual(self.owner_profile.role, UserProfile.Role.OWNER)
