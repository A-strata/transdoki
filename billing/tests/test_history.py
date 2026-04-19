"""
Тесты единой истории /billing/: объединение транзакций и периодов, фильтры.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Account
from billing.models import BillingPeriod, BillingTransaction, Plan
from billing.services.history import build_history


User = get_user_model()


def _make_user_account(name: str, balance: Decimal = Decimal("0")):
    u = User.objects.create_user(username=f"hist-{name}", password="x")
    a = Account.objects.create(name=name, owner=u, balance=balance)
    u.profile.account = a
    u.profile.save()
    return u, a


class BuildHistoryTest(TestCase):
    """Тесты build_history service: фильтры и объединение."""

    def setUp(self):
        self.user, self.account = _make_user_account("svc")

    def _tx(self, kind: str, amount: str, days_ago: int = 0):
        tx = BillingTransaction.objects.create(
            account=self.account,
            kind=kind,
            amount=Decimal(amount),
            balance_after=Decimal("100"),
            description=f"{kind} test",
        )
        # Обход auto_now_add — сдвигаем created_at в прошлое
        if days_ago:
            new_ts = timezone.now() - timedelta(days=days_ago)
            BillingTransaction.objects.filter(pk=tx.pk).update(created_at=new_ts)
            tx.refresh_from_db()
        return tx

    def _bp(self, status: str, period_start: date, total: str = "1490", plan_code: str = "start"):
        return BillingPeriod.objects.create(
            account=self.account,
            period_start=period_start,
            period_end=period_start + timedelta(days=30),
            plan_code=plan_code,
            confirmed_trips=10,
            overage_trips=0,
            subscription_fee=Decimal("1490"),
            total=Decimal(total),
            status=status,
        )

    def test_combines_transactions_and_periods_sorted_desc(self):
        self._tx("deposit", "500", days_ago=5)
        self._tx("upgrade", "1490", days_ago=3)
        self._bp("paid", date.today() - timedelta(days=60))

        events = build_history(self.account)
        self.assertEqual(len(events), 3)
        # Сортировка: свежие первые
        self.assertTrue(events[0].date >= events[1].date >= events[2].date)

    def test_draft_period_excluded(self):
        self._bp("draft", date.today() - timedelta(days=60))
        events = build_history(self.account)
        self.assertEqual(len(events), 0)

    def test_filter_credit_only(self):
        self._tx("deposit", "500")
        self._tx("upgrade", "1490")
        self._tx("refund", "100")
        events = build_history(self.account, event_type="credit")
        kinds = {e.kind for e in events}
        self.assertEqual(kinds, {"deposit", "refund"})

    def test_filter_debit_only(self):
        self._tx("deposit", "500")
        self._tx("upgrade", "1490")
        self._tx("subscription", "1490")
        self._tx("overage", "440")
        events = build_history(self.account, event_type="debit")
        kinds = {e.kind for e in events}
        self.assertEqual(kinds, {"upgrade", "subscription", "overage"})

    def test_filter_period_only(self):
        self._tx("deposit", "500")
        self._bp("paid", date.today() - timedelta(days=30))
        events = build_history(self.account, event_type="period")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, "period")

    def test_filter_specific_kind(self):
        self._tx("deposit", "500")
        self._tx("upgrade", "1490")
        events = build_history(self.account, event_type="upgrade")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, "upgrade")

    def test_filter_by_date_range(self):
        self._tx("deposit", "100", days_ago=10)
        self._tx("deposit", "200", days_ago=5)
        self._tx("deposit", "300", days_ago=1)
        today = timezone.now().date()
        events = build_history(
            self.account,
            date_from=today - timedelta(days=7),
            date_to=today,
        )
        # только 5d и 1d назад
        self.assertEqual(len(events), 2)

    def test_filter_period_status(self):
        self._bp("paid", date.today() - timedelta(days=60))
        self._bp("invoiced", date.today() - timedelta(days=30))
        events = build_history(self.account, event_type="period", period_status="invoiced")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].status, "invoiced")

    def test_period_description_contains_plan_name(self):
        self._bp("paid", date.today() - timedelta(days=30), plan_code="start")
        events = build_history(self.account)
        self.assertEqual(len(events), 1)
        # Должно быть имя плана, а не код
        self.assertIn("Старт", events[0].description)

    def test_period_description_unknown_plan_falls_back_to_code(self):
        self._bp("paid", date.today() - timedelta(days=30), plan_code="legacy_xyz")
        events = build_history(self.account)
        self.assertIn("legacy_xyz", events[0].description)

    def test_amount_direction_classification(self):
        self._tx("deposit", "500")
        self._tx("upgrade", "1490")
        self._tx("adjustment", "100")
        events = {e.kind: e for e in build_history(self.account)}
        self.assertEqual(events["deposit"].direction, "credit")
        self.assertEqual(events["upgrade"].direction, "debit")
        self.assertEqual(events["adjustment"].direction, "nominal")


@override_settings(ALLOWED_HOSTS=["*"])
class BillingHistoryViewTest(TestCase):
    """HTTP-уровень: рендеринг страницы + фильтры через GET."""

    def setUp(self):
        self.user, self.account = _make_user_account("view", balance=Decimal("1000"))
        self.client = Client()
        self.client.force_login(self.user)

    def test_renders_empty_state_for_fresh_account(self):
        r = self.client.get(reverse("billing:transactions"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "empty-state")
        self.assertContains(r, "history-filters")

    def test_filter_via_querystring(self):
        BillingTransaction.objects.create(
            account=self.account, kind="deposit",
            amount=Decimal("500"), balance_after=Decimal("500"),
        )
        BillingTransaction.objects.create(
            account=self.account, kind="upgrade",
            amount=Decimal("1490"), balance_after=Decimal("500"),
            description="Upgrade test",
        )
        r = self.client.get(reverse("billing:transactions") + "?type=credit")
        content = r.content.decode()
        self.assertIn("Пополнение", content)
        # Upgrade не должен попасть при type=credit
        self.assertNotIn("Upgrade test", content)

    def test_status_filter_for_periods(self):
        BillingPeriod.objects.create(
            account=self.account,
            period_start=date.today() - timedelta(days=60),
            period_end=date.today() - timedelta(days=30),
            plan_code="start", confirmed_trips=10, overage_trips=0,
            subscription_fee=Decimal("1490"), total=Decimal("1490"),
            status="paid",
        )
        BillingPeriod.objects.create(
            account=self.account,
            period_start=date.today() - timedelta(days=30),
            period_end=date.today(),
            plan_code="start", confirmed_trips=20, overage_trips=0,
            subscription_fee=Decimal("1490"), total=Decimal("1490"),
            status="invoiced",
        )
        r = self.client.get(
            reverse("billing:transactions") + "?type=period&status=invoiced"
        )
        content = r.content.decode()
        # Проверяем через число рейсов (20 — invoiced, 10 — paid),
        # избегая коллизий со строками в <select> фильтра.
        # <td>...20 рейсов...</td> — invoiced period, должен быть в выдаче.
        self.assertIn("20 рейсов", content)
        self.assertNotIn("10 рейсов", content)

    def test_subscription_page_no_longer_has_periods_block(self):
        """Блок 4 «Расчётные периоды» убран со страницы подписки."""
        r = self.client.get(reverse("billing:subscription"))
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        self.assertNotIn("sub-history-table", content)
        # После редизайна ссылка на полную историю переехала в шапку блока
        # «История операций» — проверяем URL, а не CSS-класс, чтобы не
        # привязываться к конкретной вёрстке.
        self.assertIn(reverse("billing:transactions"), content)
