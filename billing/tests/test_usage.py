"""
Тесты get_trip_usage — правило 24 часов и фильтр по периоду.

Покрывают 7 кейсов из §12.1 ТЗ плюс 3 граничных случая для рейсов на стыке
календарных месяцев (правило «рейс принадлежит месяцу created_at», ТЗ §3.3).

Сложность: Trip.created_at — auto_now_add, прямое задание не работает.
Используется UPDATE через all_objects.filter(pk=...).update() — обходит
auto_now_add и соответствует тому, как значения лежали бы на проде.
"""
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import Account, UserProfile
from billing.models import Plan, Subscription
from billing.services.usage import get_trip_usage
from organizations.models import Organization
from persons.models import Person
from trips.models import Trip
from vehicles.models import Vehicle


User = get_user_model()


class TripUsageTestBase(TestCase):
    """Фикстуры: аккаунт на Free + набор сущностей для создания Trip."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="u1", password="x")
        cls.account = Account.objects.create(name="A1", owner=cls.user)
        cls.user.profile.account = cls.account
        cls.user.profile.role = UserProfile.Role.OWNER
        cls.user.profile.save()

        plan_free = Plan.objects.get(code="free")
        now = timezone.now()
        Subscription.objects.update_or_create(
            account=cls.account,
            defaults={
                "plan": plan_free,
                "started_at": now,
                "current_period_start": now,
                "current_period_end": now + timedelta(days=30),
            },
        )

        # Отдельный аккаунт для проверки tenant-изоляции
        cls.other_user = User.objects.create_user(username="u2", password="x")
        cls.other_account = Account.objects.create(name="A2", owner=cls.other_user)
        cls.other_user.profile.account = cls.other_account
        cls.other_user.profile.save()
        Subscription.objects.update_or_create(
            account=cls.other_account,
            defaults={
                "plan": plan_free,
                "started_at": now,
                "current_period_start": now,
                "current_period_end": now + timedelta(days=30),
            },
        )

        # Общая фикстура сущностей для Trip
        cls.our_org = Organization.objects.create(
            full_name="Own", short_name="Own", inn="7707083893",
            is_own_company=True, created_by=cls.user, account=cls.account,
        )
        cls.carrier_org = Organization.objects.create(
            full_name="Carrier", short_name="Carrier", inn="7736050003",
            created_by=cls.user, account=cls.account,
        )
        cls.driver = Person.objects.create(
            name="N", surname="S", patronymic="P", phone="+79161234567",
            created_by=cls.user, account=cls.account,
        )
        cls.truck = Vehicle.objects.create(
            grn="А123ВС77", brand="M", vehicle_type="single",
            owner=cls.carrier_org, created_by=cls.user, account=cls.account,
        )

        # Фикстуры для other_account — аналогичные, с другими ИНН
        cls.other_our = Organization.objects.create(
            full_name="Own2", short_name="Own2", inn="7740000076",
            is_own_company=True, created_by=cls.other_user, account=cls.other_account,
        )
        cls.other_carrier = Organization.objects.create(
            full_name="Carrier2", short_name="Carrier2", inn="5024002119",
            created_by=cls.other_user, account=cls.other_account,
        )
        cls.other_driver = Person.objects.create(
            name="X", surname="Y", patronymic="Z", phone="+79161234568",
            created_by=cls.other_user, account=cls.other_account,
        )
        cls.other_truck = Vehicle.objects.create(
            grn="Б123ВС77", brand="M", vehicle_type="single",
            owner=cls.other_carrier, created_by=cls.other_user, account=cls.other_account,
        )

    def _make_trip(self, account=None, our_org=None, carrier=None, driver=None,
                   truck=None, date_of_trip=None, created_at=None, deleted_at=None):
        """
        Создаёт Trip и при необходимости ставит created_at/deleted_at через
        UPDATE (обходит auto_now_add).
        """
        account = account or self.account
        trip = Trip.objects.create(
            account=account,
            client=our_org or self.our_org,
            carrier=carrier or self.carrier_org,
            driver=driver or self.driver,
            truck=truck or self.truck,
            date_of_trip=date_of_trip or timezone.now().date(),
            cargo="Test",
            created_by=self.user if account == self.account else self.other_user,
        )
        if created_at is not None or deleted_at is not None:
            updates = {}
            if created_at is not None:
                updates["created_at"] = created_at
            if deleted_at is not None:
                updates["deleted_at"] = deleted_at
            Trip.all_objects.filter(pk=trip.pk).update(**updates)
            trip.refresh_from_db()
        return trip


class Rule24hTest(TripUsageTestBase):
    """7 кейсов §12.1 ТЗ по правилу 24 часов."""

    def setUp(self):
        self.now = timezone.now()
        # Период — последние 30 дней, хватает для всех рейсов
        self.period_start = self.now - timedelta(days=30)
        self.period_end = self.now + timedelta(days=1)

    def test_fresh_trip_is_pending(self):
        """Рейс создан <24ч назад → в pending, не в confirmed."""
        self._make_trip(created_at=self.now - timedelta(hours=5))
        usage = get_trip_usage(self.account, self.period_start, self.period_end)
        self.assertEqual(usage["confirmed"], 0)
        self.assertEqual(usage["pending"], 1)
        self.assertEqual(usage["total"], 1)

    def test_old_live_trip_is_confirmed(self):
        """Рейс создан >24ч назад, не удалён → в confirmed."""
        self._make_trip(created_at=self.now - timedelta(hours=30))
        usage = get_trip_usage(self.account, self.period_start, self.period_end)
        self.assertEqual(usage["confirmed"], 1)
        self.assertEqual(usage["pending"], 0)

    def test_trip_deleted_within_24h_of_creation_not_counted(self):
        """Рейс создан X часов назад, удалён через <24ч от create → не в confirmed."""
        created = self.now - timedelta(hours=30)
        deleted = created + timedelta(hours=10)  # 10ч < 24ч
        self._make_trip(created_at=created, deleted_at=deleted)
        usage = get_trip_usage(self.account, self.period_start, self.period_end)
        self.assertEqual(usage["confirmed"], 0)
        self.assertEqual(usage["pending"], 0)

    def test_trip_deleted_after_24h_of_creation_is_confirmed(self):
        """Рейс создан, удалён позже 24ч от create → в confirmed (тарифицируется)."""
        created = self.now - timedelta(hours=72)
        deleted = created + timedelta(hours=30)  # 30ч > 24ч
        self._make_trip(created_at=created, deleted_at=deleted)
        usage = get_trip_usage(self.account, self.period_start, self.period_end)
        self.assertEqual(usage["confirmed"], 1)
        self.assertEqual(usage["pending"], 0)

    def test_trip_from_other_period_not_counted(self):
        """Рейс с created_at вне периода — не учитывается."""
        # Период — только последние 7 дней
        narrow_start = self.now - timedelta(days=7)
        # Рейс старше периода
        self._make_trip(created_at=self.now - timedelta(days=40))
        usage = get_trip_usage(self.account, narrow_start, self.period_end)
        self.assertEqual(usage["total"], 0)

    def test_trip_from_other_account_not_counted(self):
        """Рейс другого аккаунта — не попадает в счётчик текущего."""
        self._make_trip(
            account=self.other_account,
            our_org=self.other_our,
            carrier=self.other_carrier,
            driver=self.other_driver,
            truck=self.other_truck,
            created_at=self.now - timedelta(hours=30),
        )
        usage = get_trip_usage(self.account, self.period_start, self.period_end)
        self.assertEqual(usage["total"], 0)

    def test_corporate_custom_trip_limit_none_returns_none(self):
        """Corporate с custom_trip_limit=None (или null на плане) → limit=None."""
        corp_plan = Plan.objects.get(code="corporate")
        # Corporate на seed имеет trip_limit=1200, но для теста подменяем custom=None
        self.account.subscription.plan = corp_plan
        self.account.subscription.custom_trip_limit = None
        self.account.subscription.save()
        # Проверим именно Corporate без custom_* — effective_trip_limit = plan.trip_limit = 1200
        usage = get_trip_usage(self.account, self.period_start, self.period_end)
        self.assertEqual(usage["limit"], 1200)

        # Теперь с custom_trip_limit=None И подменённым plan.trip_limit=None
        corp_plan.trip_limit = None
        corp_plan.save()
        self.account.subscription.refresh_from_db()
        usage = get_trip_usage(self.account, self.period_start, self.period_end)
        self.assertIsNone(usage["limit"])


class MonthBoundaryTest(TripUsageTestBase):
    """
    Граничные кейсы: рейс на стыке месяцев. Правило §3.3 ТЗ — рейс
    принадлежит месяцу created_at, независимо от того, когда истекло
    24-часовое окно.
    """

    def setUp(self):
        # «Сейчас» — 2026-02-02 00:30 MSK (момент ежемесячного биллинга)
        self.billing_moment = datetime(2026, 2, 2, 0, 30, tzinfo=timezone.get_current_timezone())
        # Январский период
        self.jan_start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.get_current_timezone())
        self.jan_end = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.get_current_timezone())
        # Февральский период
        self.feb_start = self.jan_end
        self.feb_end = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.get_current_timezone())

    def _at_billing_moment(self, created_at, deleted_at=None):
        """Создаёт рейс с заданными created_at/deleted_at и замораживает now."""
        from unittest.mock import patch

        trip = self._make_trip(created_at=created_at, deleted_at=deleted_at)

        # get_trip_usage использует timezone.now() для cutoff_24h. Подменяем его
        # через patch только на billing.services.usage, чтобы не влиять на прочие
        # части Django (например, на middleware и сигналы).
        return trip, patch("billing.services.usage.timezone")

    def test_month_boundary_trip_undeleted_belongs_to_january(self):
        """31.01 23:55 создан, не удалён — в январском периоде confirmed=1."""
        from unittest.mock import patch

        created_at = datetime(2026, 1, 31, 23, 55, tzinfo=timezone.get_current_timezone())
        self._make_trip(created_at=created_at)

        # «Сейчас» — момент ежемесячного биллинга 02.02 00:30
        with patch("billing.services.usage.timezone") as tz_mock:
            tz_mock.now.return_value = self.billing_moment
            jan = get_trip_usage(self.account, self.jan_start, self.jan_end)
            feb = get_trip_usage(self.account, self.feb_start, self.feb_end)

        # Возраст на момент биллинга: 24ч 35 мин > 24ч → confirmed
        self.assertEqual(jan["confirmed"], 1)
        self.assertEqual(jan["pending"], 0)
        # В феврале рейс не учитывается: created_at в январе
        self.assertEqual(feb["total"], 0)

    def test_month_boundary_trip_deleted_within_24h(self):
        """31.01 23:55 создан, 01.02 22:00 удалён (22ч от create) — не в биллинг."""
        from unittest.mock import patch

        created_at = datetime(2026, 1, 31, 23, 55, tzinfo=timezone.get_current_timezone())
        deleted_at = datetime(2026, 2, 1, 22, 0, tzinfo=timezone.get_current_timezone())
        self._make_trip(created_at=created_at, deleted_at=deleted_at)

        with patch("billing.services.usage.timezone") as tz_mock:
            tz_mock.now.return_value = self.billing_moment
            jan = get_trip_usage(self.account, self.jan_start, self.jan_end)

        # deleted_at - created_at = 22ч 5мин < 24ч → не учитывается
        self.assertEqual(jan["confirmed"], 0)
        self.assertEqual(jan["pending"], 0)

    def test_month_boundary_trip_deleted_after_24h(self):
        """31.01 23:55 создан, 02.02 10:00 удалён (34ч от create) — в январском биллинге."""
        from unittest.mock import patch

        created_at = datetime(2026, 1, 31, 23, 55, tzinfo=timezone.get_current_timezone())
        deleted_at = datetime(2026, 2, 2, 10, 0, tzinfo=timezone.get_current_timezone())
        self._make_trip(created_at=created_at, deleted_at=deleted_at)

        with patch("billing.services.usage.timezone") as tz_mock:
            tz_mock.now.return_value = self.billing_moment
            jan = get_trip_usage(self.account, self.jan_start, self.jan_end)

        # deleted_at - created_at = 34ч 5мин > 24ч → confirmed (тарифицируется)
        self.assertEqual(jan["confirmed"], 1)
