"""
Тесты activate_module / deactivate_module + ModuleRequiredMixin (ТЗ §6.7).
"""
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import Account
from billing.exceptions import InsufficientFunds, ModuleOperationError
from billing.models import AccountModule, BillingTransaction, Module, Plan, Subscription
from billing.services.balance import account_has_module
from billing.services.modules import activate_module, deactivate_module


User = get_user_model()


class ModuleFixtureMixin:
    """Создаёт аккаунт + Subscription + Module для тестов."""

    @classmethod
    def _setup_fixtures(cls):
        cls.user = User.objects.create_user(username="mod-u", password="x")
        cls.account = Account.objects.create(
            name="mod-a", owner=cls.user, balance=Decimal("1000"),
        )
        cls.user.profile.account = cls.account
        cls.user.profile.save()

        cls.plan = Plan.objects.get(code="start")
        # Период построен относительно реального now() — чтобы days_left
        # в не-замокированных тестах был положительным (для проверок
        # вроде InsufficientFunds pro_rata должен быть > 0).
        # frozen_now ниже — только для тестов на конкретную pro_rata сумму.
        now = timezone.now()
        cls.subscription, _ = Subscription.objects.update_or_create(
            account=cls.account,
            defaults={
                "plan": cls.plan,
                "started_at": now,
                "current_period_start": now - timedelta(days=10),
                "current_period_end": now + timedelta(days=20),
            },
        )
        cls.account.refresh_from_db()
        cls.frozen_now = cls.subscription.current_period_start + timedelta(days=10)

        # Делаем contracts платным для проверки pro rata
        cls.mod = Module.objects.get(code="contracts")
        cls.mod.monthly_price = Decimal("300.00")
        cls.mod.save()


class ActivateModuleTest(ModuleFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls._setup_fixtures()

    def setUp(self):
        # Для каждого теста — свежий баланс и отсутствие активных модулей
        AccountModule.objects.filter(account=self.account).delete()
        self.account.balance = Decimal("1000")
        self.account.save()

    def test_activate_charges_pro_rata(self):
        """Период 30 дней, прошло 10, осталось 20. Pro rata = 300 × 20/30 = 200."""
        with patch("billing.services.modules.timezone") as tz_mock:
            tz_mock.now.return_value = self.frozen_now
            result = activate_module(self.account, "contracts")

        self.assertEqual(result["charged"], Decimal("200.00"))
        self.assertFalse(result["already_active"])

        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("800.00"))

        am = AccountModule.objects.get(account=self.account)
        self.assertTrue(am.is_active)
        self.assertEqual(am.module.code, "contracts")

        tx = BillingTransaction.objects.get(account=self.account)
        self.assertEqual(tx.kind, BillingTransaction.Kind.MODULE)

    def test_activate_idempotent_when_already_active(self):
        """Повторный activate при is_active=True — no-op."""
        activate_module(self.account, "contracts")
        self.account.refresh_from_db()
        balance_after_first = self.account.balance

        result = activate_module(self.account, "contracts")
        self.assertTrue(result["already_active"])
        self.assertEqual(result["charged"], Decimal("0"))

        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, balance_after_first)

    def test_activate_insufficient_funds(self):
        """Баланс меньше pro rata → InsufficientFunds, модуль не активируется."""
        self.account.balance = Decimal("50")
        self.account.save()

        with self.assertRaises(InsufficientFunds):
            activate_module(self.account, "contracts")

        self.assertFalse(
            AccountModule.objects.filter(account=self.account).exists()
        )

    def test_activate_unknown_module(self):
        """Попытка активации несуществующего модуля → ModuleOperationError."""
        with self.assertRaises(ModuleOperationError):
            activate_module(self.account, "nonexistent")

    def test_activate_free_module_no_charge(self):
        """Модуль с ценой 0 ₽ активируется без списания."""
        self.mod.monthly_price = Decimal("0")
        self.mod.save()
        self.account.balance = Decimal("0")
        self.account.save()

        result = activate_module(self.account, "contracts")
        self.assertEqual(result["charged"], Decimal("0"))
        self.assertTrue(
            AccountModule.objects.filter(account=self.account, is_active=True).exists()
        )


class DeactivateModuleTest(ModuleFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls._setup_fixtures()

    def setUp(self):
        AccountModule.objects.filter(account=self.account).delete()
        self.account.balance = Decimal("1000")
        self.account.save()

    def test_deactivate_sets_ended_at_to_period_end(self):
        activate_module(self.account, "contracts")
        result = deactivate_module(self.account, "contracts")

        self.assertFalse(result["already_inactive"])
        self.assertEqual(result["active_until"], self.subscription.current_period_end)

        am = AccountModule.objects.get(account=self.account)
        self.assertFalse(am.is_active)
        self.assertEqual(am.ended_at, self.subscription.current_period_end)

    def test_deactivate_noop_when_not_active(self):
        """Повторный deactivate или без активного модуля — no-op."""
        result = deactivate_module(self.account, "contracts")
        self.assertTrue(result["already_inactive"])


class ReactivateModuleTest(ModuleFixtureMixin, TestCase):
    """Реактивация ранее отключённого модуля."""

    @classmethod
    def setUpTestData(cls):
        cls._setup_fixtures()

    def setUp(self):
        AccountModule.objects.filter(account=self.account).delete()
        self.account.balance = Decimal("1000")
        self.account.save()

    def test_reactivate_reuses_record_and_charges_pro_rata(self):
        activate_module(self.account, "contracts")
        deactivate_module(self.account, "contracts")

        am_before = AccountModule.objects.get(account=self.account)
        pk_before = am_before.pk

        # Реактивация
        result = activate_module(self.account, "contracts")
        self.assertFalse(result["already_active"])
        self.assertTrue(result["reactivated"])

        # Та же запись AccountModule, не новая
        am_after = AccountModule.objects.get(account=self.account)
        self.assertEqual(am_after.pk, pk_before)
        self.assertTrue(am_after.is_active)
        self.assertIsNone(am_after.ended_at)


class AccountHasModuleTest(ModuleFixtureMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls._setup_fixtures()

    def setUp(self):
        AccountModule.objects.filter(account=self.account).delete()

    def test_returns_false_without_activation(self):
        self.assertFalse(account_has_module(self.account, "contracts"))

    def test_returns_true_after_activate(self):
        activate_module(self.account, "contracts")
        self.assertTrue(account_has_module(self.account, "contracts"))

    def test_returns_false_after_deactivate(self):
        """После deactivate модуль сразу недоступен — is_active=False."""
        activate_module(self.account, "contracts")
        deactivate_module(self.account, "contracts")
        self.assertFalse(account_has_module(self.account, "contracts"))

    def test_exempt_bypasses(self):
        """is_billing_exempt=True → все модули считаются подключёнными."""
        self.account.is_billing_exempt = True
        self.account.save()
        self.assertTrue(account_has_module(self.account, "contracts"))
        self.assertTrue(account_has_module(self.account, "nonexistent"))
