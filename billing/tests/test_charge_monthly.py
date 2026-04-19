"""
Тесты месячного биллинга (billing.services.charging.charge_monthly).

Покрывают все кейсы §12.1 ТЗ:
1. Free с 0 рейсами → списание 0, статус paid
2. Старт с 50 рейсами → списание 1490, overage 0
3. Старт с 100 рейсами → 1490 + 20×22 = 1930
4. Бизнес с 400 рейсами → 4490 + 50×16 = 5290
5. Corporate с custom_trip_limit=None → overage = 0 независимо от рейсов
6. Недостаточно баланса → past_due, BillingPeriod invoiced
7. Повторный запуск за тот же период → no-op (idempotency)
8. Dry-run → ничего не меняет в БД
9. Активные модули увеличивают total
10. scheduled_plan применяется после успешного списания
11. is_billing_exempt=True → аккаунт пропускается

+ Граничный кейс месяца: рейс 31.01 23:55 попадает в январский BillingPeriod.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import Account, UserProfile
from billing.models import (
    AccountModule,
    BillingPeriod,
    BillingTransaction,
    Module,
    Plan,
    Subscription,
)
from billing.services.charging import charge_monthly
from organizations.models import Organization
from persons.models import Person
from trips.models import Trip
from vehicles.models import Vehicle


User = get_user_model()


class ChargeMonthlyBase(TestCase):
    """
    Общие фикстуры: аккаунт + фабрика для создания подписки с периодом,
    уже закрывшимся, чтобы charge_monthly его обработал.
    """

    @classmethod
    def setUpTestData(cls):
        # Фикс «текущего момента»: 2026-02-02 00:30 MSK —
        # совпадает с типичным временем запуска cron месячного биллинга.
        cls.billing_now = datetime(2026, 2, 2, 0, 30, tzinfo=timezone.get_current_timezone())
        # Закрывшийся период: январь 2026
        cls.period_start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.get_current_timezone())
        cls.period_end = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.get_current_timezone())

    def _make_account(self, name="A", balance: Decimal = Decimal("0"), exempt: bool = False):
        user = User.objects.create_user(username=f"u-{name}-{id(name)}", password="x")
        account = Account.objects.create(
            name=name, owner=user, is_billing_exempt=exempt, balance=balance,
        )
        user.profile.account = account
        user.profile.save()
        return account, user

    def _make_subscription(
        self,
        account,
        plan_code: str = "free",
        period_start=None,
        period_end=None,
        status: str = Subscription.Status.ACTIVE,
        custom_trip_limit=None,
        custom_overage_price=None,
    ) -> Subscription:
        plan = Plan.objects.get(code=plan_code)
        sub = Subscription.objects.create(
            account=account,
            plan=plan,
            started_at=period_start or self.period_start,
            current_period_start=period_start or self.period_start,
            current_period_end=period_end or self.period_end,
            status=status,
            custom_trip_limit=custom_trip_limit,
            custom_overage_price=custom_overage_price,
        )
        return sub

    def _trip_fixtures(self, account, user):
        """Возвращает (own_org, carrier, driver, truck) для создания рейсов."""
        own_org = Organization.objects.create(
            full_name=f"Own{account.id}", short_name=f"O{account.id}",
            inn="7707083893" if account.id % 2 else "7740000076",
            is_own_company=True, created_by=user, account=account,
        )
        carrier = Organization.objects.create(
            full_name=f"Car{account.id}", short_name=f"C{account.id}",
            inn="7736050003" if account.id % 2 else "5024002119",
            created_by=user, account=account,
        )
        driver = Person.objects.create(
            name="N", surname="S", patronymic="P",
            phone=f"+7916{account.id:07d}",
            created_by=user, account=account,
        )
        truck = Vehicle.objects.create(
            grn=f"А{account.id:03d}ВС77", brand="M", vehicle_type="single",
            owner=carrier, created_by=user, account=account,
        )
        return own_org, carrier, driver, truck

    def _seed_trips(self, account, user, count: int, inside_period: bool = True):
        """
        Создаёт `count` рейсов. inside_period=True → все с created_at в
        январе 2026 в 12:00 + возраст >24ч на момент self.billing_now.

        Возвращает список созданных Trip.
        """
        own, car, drv, trk = self._trip_fixtures(account, user)
        trips = []
        created_at = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.get_current_timezone())
        for i in range(count):
            trip = Trip.objects.create(
                account=account, client=own, carrier=car,
                driver=drv, truck=trk,
                date_of_trip=date(2026, 1, 15), cargo=f"C{i}",
                created_by=user,
            )
            # Обходим auto_now_add
            Trip.all_objects.filter(pk=trip.pk).update(created_at=created_at)
            trips.append(trip)
        return trips

    def _run_charge_monthly(self, **kwargs):
        """Запускает charge_monthly с подменённым timezone.now()."""
        with patch("billing.services.charging.timezone") as tz_mock:
            tz_mock.now.return_value = self.billing_now
            # get_trip_usage тоже использует timezone.now() для cutoff_24h
            with patch("billing.services.usage.timezone") as tz_mock2:
                tz_mock2.now.return_value = self.billing_now
                return charge_monthly(**kwargs)


class FreeTierTest(ChargeMonthlyBase):
    """Free-план: нулевой fee, статус paid при 0 рейсах."""

    def test_free_zero_trips_paid(self):
        account, _ = self._make_account("free-0")
        sub = self._make_subscription(account, "free")

        report = self._run_charge_monthly()
        self.assertEqual(report["charged"], 1)
        self.assertEqual(report["past_due"], 0)

        bp = BillingPeriod.objects.get(account=account, period_start=self.period_start.date())
        self.assertEqual(bp.total, Decimal("0"))
        self.assertEqual(bp.subscription_fee, Decimal("0"))
        self.assertEqual(bp.overage_fee, Decimal("0"))
        self.assertEqual(bp.confirmed_trips, 0)
        self.assertEqual(bp.status, BillingPeriod.Status.PAID)
        self.assertIsNotNone(bp.charged_at)

        # Баланс не изменился, транзакция не создаётся (total=0).
        account.refresh_from_db()
        self.assertEqual(account.balance, Decimal("0"))
        self.assertFalse(
            BillingTransaction.objects.filter(account=account, billing_period=bp).exists()
        )

        # Подписка перемещена на следующий месяц
        sub.refresh_from_db()
        self.assertEqual(sub.current_period_start, self.period_end)
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)


class StartPlanOverageTest(ChargeMonthlyBase):
    """Старт: 1490 ₽/мес + 22 ₽/рейс сверх 80."""

    def test_start_50_trips_no_overage(self):
        account, user = self._make_account("start-50", balance=Decimal("2000"))
        self._make_subscription(account, "start")
        self._seed_trips(account, user, 50)

        self._run_charge_monthly()

        bp = BillingPeriod.objects.get(account=account)
        self.assertEqual(bp.confirmed_trips, 50)
        self.assertEqual(bp.overage_trips, 0)
        self.assertEqual(bp.subscription_fee, Decimal("1490.00"))
        self.assertEqual(bp.overage_fee, Decimal("0"))
        self.assertEqual(bp.total, Decimal("1490.00"))

        account.refresh_from_db()
        self.assertEqual(account.balance, Decimal("510.00"))

    def test_start_100_trips_with_overage(self):
        """100 рейсов на Старте: 80 в лимите + 20 × 22 = 440 ₽ overage."""
        account, user = self._make_account("start-100", balance=Decimal("3000"))
        self._make_subscription(account, "start")
        self._seed_trips(account, user, 100)

        self._run_charge_monthly()

        bp = BillingPeriod.objects.get(account=account)
        self.assertEqual(bp.confirmed_trips, 100)
        self.assertEqual(bp.overage_trips, 20)
        self.assertEqual(bp.subscription_fee, Decimal("1490.00"))
        self.assertEqual(bp.overage_fee, Decimal("440.00"))
        self.assertEqual(bp.total, Decimal("1930.00"))

        account.refresh_from_db()
        self.assertEqual(account.balance, Decimal("1070.00"))


class BusinessPlanOverageTest(ChargeMonthlyBase):
    def test_business_400_trips(self):
        """400 рейсов на Бизнесе: 350 в лимите + 50 × 16 = 800 ₽ overage."""
        account, user = self._make_account("biz-400", balance=Decimal("6000"))
        self._make_subscription(account, "business")
        self._seed_trips(account, user, 400)

        self._run_charge_monthly()

        bp = BillingPeriod.objects.get(account=account)
        self.assertEqual(bp.confirmed_trips, 400)
        self.assertEqual(bp.overage_trips, 50)
        self.assertEqual(bp.subscription_fee, Decimal("4490.00"))
        self.assertEqual(bp.overage_fee, Decimal("800.00"))
        self.assertEqual(bp.total, Decimal("5290.00"))

        account.refresh_from_db()
        self.assertEqual(account.balance, Decimal("710.00"))


class CorporateUnlimitedTest(ChargeMonthlyBase):
    def test_corporate_custom_trip_limit_none_zero_overage(self):
        """Corporate с custom_trip_limit=None (после отключения) не даёт overage даже при 5000 рейсов."""
        # Убираем trip_limit=1200 у plan, чтобы effective_trip_limit действительно был None
        corp_plan = Plan.objects.get(code="corporate")
        corp_plan.trip_limit = None
        corp_plan.save()

        account, user = self._make_account("corp", balance=Decimal("20000"))
        self._make_subscription(account, "corporate", custom_trip_limit=None)
        self._seed_trips(account, user, 500)

        self._run_charge_monthly()

        bp = BillingPeriod.objects.get(account=account)
        self.assertEqual(bp.confirmed_trips, 500)
        self.assertEqual(bp.overage_trips, 0)
        self.assertIsNone(bp.trip_limit)
        self.assertEqual(bp.overage_fee, Decimal("0"))
        self.assertEqual(bp.subscription_fee, Decimal("11990.00"))
        self.assertEqual(bp.total, Decimal("11990.00"))


class InsufficientBalanceTest(ChargeMonthlyBase):
    def test_past_due_when_balance_not_enough(self):
        """Start-подписка, баланс 0 → past_due, BillingPeriod invoiced."""
        account, _ = self._make_account("no-balance", balance=Decimal("0"))
        sub = self._make_subscription(account, "start")

        report = self._run_charge_monthly()
        self.assertEqual(report["past_due"], 1)
        self.assertEqual(report["charged"], 0)

        bp = BillingPeriod.objects.get(account=account)
        self.assertEqual(bp.status, BillingPeriod.Status.INVOICED)
        self.assertIsNone(bp.charged_at)
        self.assertEqual(bp.total, Decimal("1490.00"))

        # Баланс не тронут, BillingTransaction не создан
        account.refresh_from_db()
        self.assertEqual(account.balance, Decimal("0"))
        self.assertFalse(
            BillingTransaction.objects.filter(account=account, billing_period=bp).exists()
        )

        # Подписка в past_due с проставленным past_due_since
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.PAST_DUE)
        self.assertIsNotNone(sub.past_due_since)


class IdempotencyTest(ChargeMonthlyBase):
    def test_repeat_run_is_noop(self):
        """Повторный charge_monthly за тот же период — ничего не делает."""
        account, _ = self._make_account("idem")
        self._make_subscription(account, "free")

        self._run_charge_monthly()
        self.assertEqual(BillingPeriod.objects.filter(account=account).count(), 1)

        # Для второго запуска период уже был продвинут вперёд — значит
        # current_period_end > now, и вторая подписка не попадёт в выборку.
        # Проверяем именно это.
        report2 = self._run_charge_monthly()
        self.assertEqual(report2["processed"], 0)
        self.assertEqual(BillingPeriod.objects.filter(account=account).count(), 1)

    def test_idempotent_even_if_period_not_advanced(self):
        """
        Искусственный случай: BillingPeriod уже есть, но подписка остановилась
        на старом периоде (ручная интервенция). charge_monthly должен пропустить.
        """
        account, _ = self._make_account("idem2")
        sub = self._make_subscription(account, "free")
        # Создаём BillingPeriod руками — эмулируем предыдущий запуск
        BillingPeriod.objects.create(
            account=account,
            period_start=sub.current_period_start.date(),
            period_end=sub.current_period_end.date(),
            plan_code="free",
            confirmed_trips=0,
            overage_trips=0,
            subscription_fee=Decimal("0"),
            total=Decimal("0"),
            status=BillingPeriod.Status.PAID,
        )

        report = self._run_charge_monthly()
        self.assertEqual(report["skipped"], 1)
        # BillingPeriod так и один
        self.assertEqual(BillingPeriod.objects.filter(account=account).count(), 1)


class DryRunTest(ChargeMonthlyBase):
    def test_dry_run_no_db_changes(self):
        account, user = self._make_account("dry", balance=Decimal("2000"))
        self._make_subscription(account, "start")
        self._seed_trips(account, user, 50)

        original_balance = account.balance
        self._run_charge_monthly(dry_run=True)

        account.refresh_from_db()
        self.assertEqual(account.balance, original_balance)
        self.assertFalse(BillingPeriod.objects.filter(account=account).exists())
        self.assertFalse(BillingTransaction.objects.filter(account=account).exists())


class ModulesChargeTest(ChargeMonthlyBase):
    def test_active_modules_add_to_total(self):
        """Активные модули добавляются в total и в modules_snapshot."""
        # Делаем contracts платным для теста
        mod = Module.objects.get(code="contracts")
        mod.monthly_price = Decimal("490.00")
        mod.save()

        account, _ = self._make_account("mod", balance=Decimal("3000"))
        self._make_subscription(account, "start")
        AccountModule.objects.create(account=account, module=mod, is_active=True)

        self._run_charge_monthly()

        bp = BillingPeriod.objects.get(account=account)
        self.assertEqual(bp.subscription_fee, Decimal("1490.00"))
        self.assertEqual(bp.modules_fee, Decimal("490.00"))
        self.assertEqual(bp.total, Decimal("1980.00"))
        self.assertEqual(
            bp.modules_snapshot,
            [{"code": "contracts", "price": "490.00"}],
        )

    def test_inactive_modules_not_charged(self):
        """Модуль с is_active=False не попадает в списание."""
        mod = Module.objects.get(code="contracts")
        mod.monthly_price = Decimal("490.00")
        mod.save()

        account, _ = self._make_account("mod-off", balance=Decimal("2000"))
        self._make_subscription(account, "start")
        AccountModule.objects.create(account=account, module=mod, is_active=False)

        self._run_charge_monthly()

        bp = BillingPeriod.objects.get(account=account)
        self.assertEqual(bp.modules_fee, Decimal("0"))
        self.assertEqual(bp.modules_snapshot, [])


class ScheduledDowngradeTest(ChargeMonthlyBase):
    def test_scheduled_plan_applied_after_successful_charge(self):
        """scheduled_plan применяется после успешного списания за текущий период."""
        account, _ = self._make_account("down", balance=Decimal("6000"))
        sub = self._make_subscription(account, "business")
        sub.scheduled_plan = Plan.objects.get(code="start")
        sub.save()

        self._run_charge_monthly()

        sub.refresh_from_db()
        # Списано за бизнес (4490) — текущий план
        bp = BillingPeriod.objects.get(account=account)
        self.assertEqual(bp.plan_code, "business")
        self.assertEqual(bp.subscription_fee, Decimal("4490.00"))
        # Но на следующий период подписка уже на start
        self.assertEqual(sub.plan.code, "start")
        self.assertIsNone(sub.scheduled_plan_id)

    def test_scheduled_plan_not_applied_when_past_due(self):
        """При нехватке баланса scheduled_plan не применяется — клиент сначала платит."""
        account, _ = self._make_account("down-pd", balance=Decimal("0"))
        sub = self._make_subscription(account, "business")
        sub.scheduled_plan = Plan.objects.get(code="start")
        sub.save()

        self._run_charge_monthly()

        sub.refresh_from_db()
        self.assertEqual(sub.plan.code, "business")  # остаётся на старом
        self.assertEqual(sub.scheduled_plan.code, "start")  # не сброшен
        self.assertEqual(sub.status, Subscription.Status.PAST_DUE)


class ExemptSkipTest(ChargeMonthlyBase):
    def test_exempt_account_skipped(self):
        """is_billing_exempt=True: BillingPeriod не создаётся, период не двигается."""
        account, _ = self._make_account("ex", exempt=True, balance=Decimal("0"))
        sub = self._make_subscription(account, "business")
        original_end = sub.current_period_end

        report = self._run_charge_monthly()
        self.assertEqual(report["skipped"], 1)
        self.assertEqual(report["charged"], 0)

        self.assertFalse(BillingPeriod.objects.filter(account=account).exists())
        sub.refresh_from_db()
        self.assertEqual(sub.current_period_end, original_end)
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)


class MonthBoundaryInChargeMonthlyTest(ChargeMonthlyBase):
    def test_trip_at_month_boundary_counts_in_january_period(self):
        """Рейс 31.01 23:55 включается в январский BillingPeriod."""
        account, user = self._make_account("boundary", balance=Decimal("2000"))
        self._make_subscription(account, "start")

        own, car, drv, trk = self._trip_fixtures(account, user)
        # Рейс на самом краю января: 23:55
        trip = Trip.objects.create(
            account=account, client=own, carrier=car, driver=drv, truck=trk,
            date_of_trip=date(2026, 1, 31), cargo="boundary",
            created_by=user,
        )
        boundary_time = datetime(2026, 1, 31, 23, 55, tzinfo=timezone.get_current_timezone())
        Trip.all_objects.filter(pk=trip.pk).update(created_at=boundary_time)

        # Биллинг-момент 02.02 00:30 → возраст рейса 24ч35мин, уже confirmed
        self._run_charge_monthly()

        bp = BillingPeriod.objects.get(account=account)
        self.assertEqual(bp.period_start, date(2026, 1, 1))
        self.assertEqual(bp.confirmed_trips, 1)


class OnlyAccountIdFilterTest(ChargeMonthlyBase):
    def test_account_id_restricts_scope(self):
        """--account-id ограничивает обработку одним аккаунтом."""
        a1, _ = self._make_account("a1")
        a2, _ = self._make_account("a2")
        self._make_subscription(a1, "free")
        self._make_subscription(a2, "free")

        report = self._run_charge_monthly(account_id=a1.id)
        self.assertEqual(report["processed"], 1)
        self.assertTrue(BillingPeriod.objects.filter(account=a1).exists())
        self.assertFalse(BillingPeriod.objects.filter(account=a2).exists())


class TransactionCorrectnessTest(ChargeMonthlyBase):
    def test_billing_transaction_fields(self):
        """Созданная BillingTransaction имеет корректные kind, amount, balance_after, billing_period."""
        account, _ = self._make_account("tx", balance=Decimal("2000"))
        self._make_subscription(account, "start")

        self._run_charge_monthly()

        bp = BillingPeriod.objects.get(account=account)
        tx = BillingTransaction.objects.get(account=account, billing_period=bp)
        self.assertEqual(tx.kind, BillingTransaction.Kind.SUBSCRIPTION)
        self.assertEqual(tx.amount, Decimal("1490.00"))
        self.assertEqual(tx.balance_after, Decimal("510.00"))
        self.assertIn("Старт", tx.description)
        self.assertIn("2026-01-01", tx.description)
