from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

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
