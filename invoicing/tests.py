from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import Account, UserProfile
from organizations.models import Organization
from persons.models import Person
from trips.models import Trip, TripPoint
from vehicles.models import Vehicle

from .models import Act, Invoice, InvoiceLine
from .services import (
    apply_discount_to_invoice,
    cancel_invoice,
    create_act_from_invoice,
    create_invoice_from_trips,
    next_act_number,
    next_invoice_number,
    prepare_invoice_data,
)


class InvoicingTestBase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123",
        )
        self.account = Account.objects.create(name="Тест-аккаунт", owner=self.user)
        self.user.profile.account = self.account
        self.user.profile.role = UserProfile.Role.OWNER
        self.user.profile.save()

        self.org_client = Organization.objects.create(
            full_name='ООО "Заказчик"',
            short_name="Заказчик",
            inn="7707083893",
            account=self.account,
            created_by=self.user,
        )
        self.org_carrier = Organization.objects.create(
            full_name='ООО "Перевозчик"',
            short_name="Перевозчик",
            inn="7736050003",
            account=self.account,
            created_by=self.user,
        )
        self.driver = Person.objects.create(
            name="Пётр", surname="Петров",
            phone="+79161234567",
            account=self.account,
            created_by=self.user,
        )
        self.truck = Vehicle.objects.create(
            grn="А123ВС77", brand="МАЗ", vehicle_type="single",
            owner=self.org_carrier,
            account=self.account,
            created_by=self.user,
        )

    def _create_trip(self, client=None, cost=None):
        trip = Trip.objects.create(
            account=self.account,
            date_of_trip=date(2026, 5, 1),
            client=client or self.org_client,
            carrier=self.org_carrier,
            driver=self.driver,
            truck=self.truck,
            cargo="Груз",
            client_cost=cost if cost is not None else Decimal("10000"),
            client_cost_unit="rub",
            created_by=self.user,
        )
        TripPoint.objects.create(
            trip=trip, point_type="LOAD", sequence=1,
            address="Москва, ул. Тестовая 1",
            planned_date=date(2026, 5, 1),
        )
        TripPoint.objects.create(
            trip=trip, point_type="UNLOAD", sequence=2,
            address="Казань, ул. Мира 5",
            planned_date=date(2026, 5, 2),
        )
        return trip


# ────────────────────────────────────────────────
# InvoiceLine.compute()
# ────────────────────────────────────────────────

class InvoiceLineComputeTest(TestCase):

    def _make_line(self, **kwargs):
        line = InvoiceLine(**kwargs)
        return line

    def test_discount_pct(self):
        line = self._make_line(unit_price=Decimal("1000"), discount_pct=Decimal("10"))
        line.compute(last_edited="pct")
        self.assertEqual(line.discount_amount, Decimal("100.00"))
        self.assertEqual(line.amount_net, Decimal("900.00"))
        self.assertEqual(line.vat_amount, Decimal("0.00"))
        self.assertEqual(line.amount_total, Decimal("900.00"))

    def test_discount_amount(self):
        line = self._make_line(
            unit_price=Decimal("1000"), discount_amount=Decimal("150"),
        )
        line.compute(last_edited="amount")
        self.assertEqual(line.discount_pct, Decimal("15.00"))
        self.assertEqual(line.amount_net, Decimal("850.00"))

    def test_vat_20(self):
        line = self._make_line(
            unit_price=Decimal("1000"), discount_pct=Decimal("0"), vat_rate=20,
        )
        line.compute()
        self.assertEqual(line.amount_net, Decimal("1000.00"))
        self.assertEqual(line.vat_amount, Decimal("200.00"))
        self.assertEqual(line.amount_total, Decimal("1200.00"))

    def test_zero_price(self):
        line = self._make_line(unit_price=Decimal("0"))
        line.compute()
        self.assertEqual(line.amount_net, Decimal("0"))
        self.assertEqual(line.vat_amount, Decimal("0"))
        self.assertEqual(line.amount_total, Decimal("0"))
        self.assertEqual(line.discount_pct, Decimal("0"))
        self.assertEqual(line.discount_amount, Decimal("0"))

    def test_rounding(self):
        line = self._make_line(
            unit_price=Decimal("100"), discount_pct=Decimal("3"),
        )
        line.compute()
        self.assertEqual(line.discount_amount, Decimal("3.00"))
        self.assertEqual(line.amount_net, Decimal("97.00"))


# ────────────────────────────────────────────────
# next_invoice_number / next_act_number
# ────────────────────────────────────────────────

class NumberingTest(InvoicingTestBase):

    def test_first_invoice_number(self):
        year = date.today().year
        num = next_invoice_number(self.account)
        self.assertEqual(num, f"СЧ-{year}-0001")

    def test_second_invoice_number(self):
        year = date.today().year
        Invoice.objects.create(
            account=self.account, created_by=self.user,
            number=f"СЧ-{year}-0001", date=date.today(),
            customer=self.org_client,
        )
        num = next_invoice_number(self.account)
        self.assertEqual(num, f"СЧ-{year}-0002")

    def test_cancelled_does_not_reset_numbering(self):
        year = date.today().year
        inv = Invoice.objects.create(
            account=self.account, created_by=self.user,
            number=f"СЧ-{year}-0001", date=date.today(),
            customer=self.org_client,
        )
        inv.status = Invoice.Status.CANCELLED
        inv.save(update_fields=["status"])

        num = next_invoice_number(self.account)
        self.assertEqual(num, f"СЧ-{year}-0002")

    def test_first_act_number(self):
        year = date.today().year
        num = next_act_number(self.account)
        self.assertEqual(num, f"АКТ-{year}-0001")


# ────────────────────────────────────────────────
# prepare_invoice_data
# ────────────────────────────────────────────────

class PrepareInvoiceDataTest(InvoicingTestBase):

    def test_returns_prefilled_data(self):
        trip = self._create_trip(cost=Decimal("5000"))
        data = prepare_invoice_data(self.account, [trip.pk])
        self.assertEqual(data["customer"], self.org_client)
        self.assertEqual(len(data["lines"]), 1)
        self.assertEqual(len(data["trips"]), 1)
        line = data["lines"][0]
        self.assertEqual(line.unit_price, Decimal("5000"))
        self.assertEqual(line.amount_net, Decimal("5000.00"))
        self.assertIsNone(line.pk)

    def test_does_not_write_to_db(self):
        trip = self._create_trip(cost=Decimal("5000"))
        invoice_count_before = Invoice.objects.count()
        line_count_before = InvoiceLine.objects.count()
        prepare_invoice_data(self.account, [trip.pk])
        self.assertEqual(Invoice.objects.count(), invoice_count_before)
        self.assertEqual(InvoiceLine.objects.count(), line_count_before)

    def test_different_customers_raises(self):
        t1 = self._create_trip(client=self.org_client, cost=Decimal("1000"))
        t2 = self._create_trip(client=self.org_carrier, cost=Decimal("2000"))
        with self.assertRaises(ValueError):
            prepare_invoice_data(self.account, [t1.pk, t2.pk])

    def test_already_invoiced_raises(self):
        trip = self._create_trip(cost=Decimal("5000"))
        create_invoice_from_trips(self.account, [trip.pk], self.user)
        with self.assertRaises(ValueError):
            prepare_invoice_data(self.account, [trip.pk])

    def test_no_cost_raises(self):
        trip = self._create_trip()
        trip.client_cost = None
        trip.save(update_fields=["client_cost"])
        with self.assertRaises(ValueError):
            prepare_invoice_data(self.account, [trip.pk])

    def test_empty_trip_ids_raises(self):
        with self.assertRaises(ValueError):
            prepare_invoice_data(self.account, [])


# ────────────────────────────────────────────────
# create_invoice_from_trips
# ────────────────────────────────────────────────

class CreateInvoiceFromTripsTest(InvoicingTestBase):

    def test_single_trip(self):
        trip = self._create_trip(cost=Decimal("5000"))
        invoice = create_invoice_from_trips(
            self.account, [trip.pk], self.user,
        )
        self.assertEqual(invoice.status, Invoice.Status.DRAFT)
        self.assertEqual(invoice.customer_id, self.org_client.pk)
        self.assertEqual(invoice.lines.count(), 1)

        line = invoice.lines.first()
        self.assertEqual(line.unit_price, Decimal("5000"))
        self.assertEqual(line.trip_id, trip.pk)

    def test_multiple_trips_same_customer(self):
        t1 = self._create_trip(cost=Decimal("3000"))
        t2 = self._create_trip(cost=Decimal("7000"))
        invoice = create_invoice_from_trips(
            self.account, [t1.pk, t2.pk], self.user,
        )
        self.assertEqual(invoice.lines.count(), 2)
        self.assertEqual(invoice.total, Decimal("10000.00"))

    def test_different_customers_raises(self):
        t1 = self._create_trip(client=self.org_client, cost=Decimal("1000"))
        t2 = self._create_trip(client=self.org_carrier, cost=Decimal("2000"))
        with self.assertRaises(ValueError):
            create_invoice_from_trips(
                self.account, [t1.pk, t2.pk], self.user,
            )

    def test_already_invoiced_raises(self):
        trip = self._create_trip(cost=Decimal("5000"))
        create_invoice_from_trips(self.account, [trip.pk], self.user)
        with self.assertRaises(ValueError):
            create_invoice_from_trips(self.account, [trip.pk], self.user)

    def test_no_cost_raises(self):
        trip = self._create_trip()
        trip.client_cost = None
        trip.save(update_fields=["client_cost"])
        with self.assertRaises(ValueError):
            create_invoice_from_trips(self.account, [trip.pk], self.user)

    def test_empty_trip_ids_raises(self):
        with self.assertRaises(ValueError):
            create_invoice_from_trips(self.account, [], self.user)

    def test_with_lines_data(self):
        trip = self._create_trip(cost=Decimal("5000"))
        lines_data = [{
            "trip_id": trip.pk,
            "description": "Пользовательское описание",
            "unit_price": Decimal("4500"),
            "discount_pct": Decimal("10"),
            "vat_rate": 20,
        }]
        invoice = create_invoice_from_trips(
            self.account, [trip.pk], self.user, lines_data=lines_data,
        )
        line = invoice.lines.first()
        self.assertEqual(line.description, "Пользовательское описание")
        self.assertEqual(line.unit_price, Decimal("4500"))
        self.assertEqual(line.discount_pct, Decimal("10"))
        self.assertEqual(line.vat_rate, 20)
        self.assertEqual(line.amount_net, Decimal("4050.00"))


# ────────────────────────────────────────────────
# apply_discount_to_invoice
# ────────────────────────────────────────────────

class ApplyDiscountTest(InvoicingTestBase):

    def test_applies_to_service_lines(self):
        trip = self._create_trip(cost=Decimal("1000"))
        invoice = create_invoice_from_trips(
            self.account, [trip.pk], self.user,
        )
        apply_discount_to_invoice(invoice, Decimal("10"), self.user)

        line = invoice.lines.get(kind=InvoiceLine.Kind.SERVICE)
        self.assertEqual(line.discount_pct, Decimal("10"))
        self.assertEqual(line.amount_net, Decimal("900.00"))
        self.assertEqual(line.amount_total, Decimal("900.00"))

    def test_does_not_touch_penalty_lines(self):
        trip = self._create_trip(cost=Decimal("1000"))
        invoice = create_invoice_from_trips(
            self.account, [trip.pk], self.user,
        )
        penalty = InvoiceLine(
            invoice=invoice, kind=InvoiceLine.Kind.PENALTY,
            description="Штраф", unit_price=Decimal("500"),
            discount_pct=Decimal("0"), vat_rate=0,
        )
        penalty.compute()
        penalty.save()

        apply_discount_to_invoice(invoice, Decimal("20"), self.user)

        penalty.refresh_from_db()
        self.assertEqual(penalty.discount_pct, Decimal("0"))
        self.assertEqual(penalty.amount_net, Decimal("500.00"))

    def test_non_draft_raises(self):
        trip = self._create_trip(cost=Decimal("1000"))
        invoice = create_invoice_from_trips(
            self.account, [trip.pk], self.user,
        )
        invoice.status = Invoice.Status.SENT
        invoice.save(update_fields=["status"])

        with self.assertRaises(ValueError):
            apply_discount_to_invoice(invoice, Decimal("10"), self.user)


# ────────────────────────────────────────────────
# cancel_invoice
# ────────────────────────────────────────────────

class CancelInvoiceTest(InvoicingTestBase):

    def test_sets_cancelled(self):
        trip = self._create_trip(cost=Decimal("1000"))
        invoice = create_invoice_from_trips(
            self.account, [trip.pk], self.user,
        )
        cancel_invoice(invoice, self.user)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.CANCELLED)

    def test_deletes_lines(self):
        trip = self._create_trip(cost=Decimal("1000"))
        invoice = create_invoice_from_trips(
            self.account, [trip.pk], self.user,
        )
        cancel_invoice(invoice, self.user)
        self.assertEqual(invoice.lines.count(), 0)

    def test_trip_available_after_cancel(self):
        trip = self._create_trip(cost=Decimal("1000"))
        invoice = create_invoice_from_trips(
            self.account, [trip.pk], self.user,
        )
        cancel_invoice(invoice, self.user)

        new_invoice = create_invoice_from_trips(
            self.account, [trip.pk], self.user,
        )
        self.assertEqual(new_invoice.lines.count(), 1)

    def test_paid_raises(self):
        trip = self._create_trip(cost=Decimal("1000"))
        invoice = create_invoice_from_trips(
            self.account, [trip.pk], self.user,
        )
        invoice.status = Invoice.Status.PAID
        invoice.save(update_fields=["status"])

        with self.assertRaises(ValueError):
            cancel_invoice(invoice, self.user)


# ────────────────────────────────────────────────
# create_act_from_invoice
# ────────────────────────────────────────────────

class CreateActFromInvoiceTest(InvoicingTestBase):

    def test_creates_act_with_sums(self):
        trip = self._create_trip(cost=Decimal("5000"))
        invoice = create_invoice_from_trips(
            self.account, [trip.pk], self.user,
        )
        act = create_act_from_invoice(invoice, self.user)
        self.assertTrue(Act.objects.filter(pk=act.pk).exists())
        self.assertEqual(act.amount_net, invoice.total_net)
        self.assertEqual(act.vat_amount, invoice.total_vat)
        self.assertEqual(act.amount_total, invoice.total)
        self.assertEqual(act.invoice_id, invoice.pk)
        self.assertEqual(act.account_id, self.account.pk)

    def test_description_single_trip(self):
        trip = self._create_trip(cost=Decimal("5000"))
        invoice = create_invoice_from_trips(
            self.account, [trip.pk], self.user,
        )
        act = create_act_from_invoice(invoice, self.user)
        self.assertIn("Москва", act.description)
        self.assertIn("Казань", act.description)
        self.assertIn("01.05.2026", act.description)

    def test_description_multiple_trips(self):
        t1 = self._create_trip(cost=Decimal("3000"))
        t2 = self._create_trip(cost=Decimal("7000"))
        invoice = create_invoice_from_trips(
            self.account, [t1.pk, t2.pk], self.user,
        )
        act = create_act_from_invoice(invoice, self.user)
        self.assertIn("2 рейса", act.description)
        self.assertIn(invoice.number, act.description)

    def test_duplicate_raises(self):
        trip = self._create_trip(cost=Decimal("5000"))
        invoice = create_invoice_from_trips(
            self.account, [trip.pk], self.user,
        )
        create_act_from_invoice(invoice, self.user)
        self.assertEqual(Act.objects.filter(invoice=invoice).count(), 1)
        with self.assertRaises(ValueError):
            create_act_from_invoice(invoice, self.user)
        self.assertEqual(Act.objects.filter(invoice=invoice).count(), 1)

    def test_act_sums_frozen(self):
        trip = self._create_trip(cost=Decimal("5000"))
        invoice = create_invoice_from_trips(
            self.account, [trip.pk], self.user,
        )
        act = create_act_from_invoice(invoice, self.user)
        original_total = act.amount_total

        line = invoice.lines.first()
        line.unit_price = Decimal("9999")
        line.compute()
        line.save()

        act.refresh_from_db()
        self.assertEqual(act.amount_total, original_total)
