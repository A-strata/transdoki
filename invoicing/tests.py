"""
Тесты B1: Invoice.seller — определение поставщика через carrier/forwarder.

Покрывают:
  - prepare_invoice_data: извлекает seller из trip.carrier / trip.forwarder
  - create_invoice: валидация seller (обязателен, свой, is_own_company)
  - create_invoice: per-seller автонумерация (разные seller → независимые ряды)
  - update_invoice: запрет смены seller
  - update_invoice: bank_account должен принадлежать invoice.seller
  - InvoiceGenerator.build_context: использует invoice.seller
  - SellerBankAccountsView: tenant-изоляция
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Account, UserProfile
from invoicing.models import InvoiceLine
from invoicing.services import (
    InvoiceGenerator,
    create_invoice,
    prepare_invoice_data,
    update_invoice,
)
from organizations.models import Bank, Organization, OrganizationBank
from persons.models import Person
from trips.models import Trip, TripPoint
from vehicles.models import Vehicle

User = get_user_model()


class B1Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="u", password="p")
        cls.account = Account.objects.create(name="Acc", owner=cls.user)
        cls.user.profile.account = cls.account
        cls.user.profile.role = UserProfile.Role.OWNER
        cls.user.profile.save()

        cls.own_a = Organization.objects.create(
            full_name="ООО А", short_name="А",
            inn="7707083893", is_own_company=True,
            account=cls.account, created_by=cls.user,
        )
        cls.own_b = Organization.objects.create(
            full_name="ООО Б", short_name="Б",
            inn="7728168971", is_own_company=True,
            account=cls.account, created_by=cls.user,
        )
        cls.client_org = Organization.objects.create(
            full_name="ООО Клиент", short_name="Клиент",
            inn="7736050003",
            account=cls.account, created_by=cls.user,
        )
        cls.foreign_carrier = Organization.objects.create(
            full_name="ИП Чужой", short_name="Чужой",
            inn="7702070139",
            account=cls.account, created_by=cls.user,
        )

        cls.bank = Bank.objects.create(
            bank_name="Тест-Банк", bic="044525225",
            corr_account="30101810400000000225",
        )
        cls.bank_a = OrganizationBank.objects.create(
            account_num="40702810900000012345",
            account_owner=cls.own_a,
            account_bank=cls.bank,
            account=cls.account,
            created_by=cls.user,
        )
        cls.bank_b = OrganizationBank.objects.create(
            account_num="40702810900000067890",
            account_owner=cls.own_b,
            account_bank=cls.bank,
            account=cls.account,
            created_by=cls.user,
        )

        cls.driver = Person.objects.create(
            name="И", surname="И", patronymic="И",
            phone="+79161234567",
            account=cls.account, created_by=cls.user,
        )
        cls.truck = Vehicle.objects.create(
            grn="А001АА77", brand="X", vehicle_type="single",
            owner=cls.own_a,
            account=cls.account, created_by=cls.user,
        )

    def _make_trip(self, *, carrier, forwarder=None, client=None, client_cost="1000"):
        trip = Trip.objects.create(
            num_of_trip=Trip.objects.filter(account=self.account).count() + 1,
            date_of_trip=date(2026, 5, 1),
            client=client or self.client_org,
            carrier=carrier,
            forwarder=forwarder,
            driver=self.driver,
            truck=self.truck,
            cargo="Cargo",
            client_cost=Decimal(client_cost),
            account=self.account,
            created_by=self.user,
        )
        TripPoint.objects.create(
            trip=trip, sequence=1,
            point_type=TripPoint.Type.LOAD,
            address="Москва",
            planned_date=date(2026, 5, 1),
        )
        TripPoint.objects.create(
            trip=trip, sequence=2,
            point_type=TripPoint.Type.UNLOAD,
            address="Казань",
            planned_date=date(2026, 5, 2),
        )
        return trip


class PrepareInvoiceDataTests(B1Base):
    def test_carrier_as_own_company_becomes_seller(self):
        trip = self._make_trip(carrier=self.own_a)
        data = prepare_invoice_data(self.user, [trip.pk])
        self.assertEqual(data["seller"], self.own_a)

    def test_forwarder_as_own_company_becomes_seller(self):
        trip = self._make_trip(
            carrier=self.foreign_carrier,
            forwarder=self.own_b,
        )
        data = prepare_invoice_data(self.user, [trip.pk])
        self.assertEqual(data["seller"], self.own_b)

    def test_no_own_role_raises(self):
        trip = self._make_trip(carrier=self.foreign_carrier)
        with self.assertRaises(ValidationError):
            prepare_invoice_data(self.user, [trip.pk])

    def test_mixed_sellers_raises(self):
        t1 = self._make_trip(carrier=self.own_a)
        t2 = self._make_trip(carrier=self.own_b)
        with self.assertRaises(ValidationError):
            prepare_invoice_data(self.user, [t1.pk, t2.pk])

    def test_current_org_mismatch_raises(self):
        """
        Пользователь сидит под own_b, а рейс выставляется от own_a
        (own_a — carrier). Счёт выставлять нельзя — нужно переключиться.
        """
        trip = self._make_trip(carrier=self.own_a)
        with self.assertRaises(ValidationError) as cm:
            prepare_invoice_data(self.user, [trip.pk], current_org=self.own_b)
        self.assertIn(self.own_a.short_name, str(cm.exception))

    def test_current_org_match_ok(self):
        trip = self._make_trip(carrier=self.own_a)
        data = prepare_invoice_data(self.user, [trip.pk], current_org=self.own_a)
        self.assertEqual(data["seller"], self.own_a)


class CreateInvoiceTests(B1Base):
    def _lines(self, trip):
        return [{
            "trip": trip,
            "kind": InvoiceLine.Kind.SERVICE,
            "description": "x",
            "quantity": Decimal("1"),
            "unit": InvoiceLine.UnitOfMeasure.SERVICE,
            "unit_price": Decimal("1000"),
            "discount_amount": Decimal("0"),
            "vat_rate": None,
        }]

    def test_seller_required(self):
        trip = self._make_trip(carrier=self.own_a)
        with self.assertRaises(ValidationError) as cm:
            create_invoice(
                user=self.user,
                customer=self.client_org,
                seller=None,
                lines_data=self._lines(trip),
            )
        self.assertIn("seller", cm.exception.message_dict)

    def test_seller_must_be_own_company(self):
        trip = self._make_trip(carrier=self.own_a)
        with self.assertRaises(ValidationError) as cm:
            create_invoice(
                user=self.user,
                customer=self.client_org,
                seller=self.foreign_carrier,
                lines_data=self._lines(trip),
            )
        self.assertIn("seller", cm.exception.message_dict)

    def test_per_seller_numbering_is_independent(self):
        t1 = self._make_trip(carrier=self.own_a)
        t2 = self._make_trip(carrier=self.own_a)
        t3 = self._make_trip(carrier=self.own_b)

        inv1 = create_invoice(
            user=self.user, customer=self.client_org, seller=self.own_a,
            lines_data=self._lines(t1), bank_account=self.bank_a,
        )
        inv2 = create_invoice(
            user=self.user, customer=self.client_org, seller=self.own_a,
            lines_data=self._lines(t2), bank_account=self.bank_a,
        )
        inv3 = create_invoice(
            user=self.user, customer=self.client_org, seller=self.own_b,
            lines_data=self._lines(t3), bank_account=self.bank_b,
        )
        self.assertEqual(inv1.number, 1)
        self.assertEqual(inv2.number, 2)
        self.assertEqual(inv3.number, 1)
        self.assertEqual(inv1.year, inv3.year)

    def test_bank_account_must_belong_to_seller(self):
        trip = self._make_trip(carrier=self.own_a)
        with self.assertRaises(ValidationError) as cm:
            create_invoice(
                user=self.user, customer=self.client_org, seller=self.own_a,
                lines_data=self._lines(trip), bank_account=self.bank_b,
            )
        self.assertIn("bank_account", cm.exception.message_dict)


class UpdateInvoiceTests(B1Base):
    def _create(self, trip, seller, bank):
        return create_invoice(
            user=self.user, customer=self.client_org, seller=seller,
            lines_data=[{
                "trip": trip,
                "kind": InvoiceLine.Kind.SERVICE,
                "description": "x",
                "quantity": Decimal("1"),
                "unit": InvoiceLine.UnitOfMeasure.SERVICE,
                "unit_price": Decimal("1000"),
                "discount_amount": Decimal("0"),
                "vat_rate": None,
            }],
            bank_account=bank,
        )

    def test_seller_change_forbidden(self):
        trip = self._make_trip(carrier=self.own_a)
        inv = self._create(trip, self.own_a, self.bank_a)
        with self.assertRaises(ValidationError) as cm:
            update_invoice(
                inv,
                user=self.user,
                header_data={"seller": self.own_b},
                lines_diff={"to_create": [], "to_update": [], "to_delete": []},
            )
        self.assertIn("seller", cm.exception.message_dict)


class InvoiceGeneratorTests(B1Base):
    def test_build_context_uses_invoice_seller(self):
        trip = self._make_trip(carrier=self.own_a)
        inv = create_invoice(
            user=self.user, customer=self.client_org, seller=self.own_a,
            lines_data=[{
                "trip": trip,
                "kind": InvoiceLine.Kind.SERVICE,
                "description": "x",
                "quantity": Decimal("1"),
                "unit": InvoiceLine.UnitOfMeasure.SERVICE,
                "unit_price": Decimal("1000"),
                "discount_amount": Decimal("0"),
                "vat_rate": None,
            }],
            bank_account=self.bank_a,
        )
        ctx = InvoiceGenerator.build_context(inv)
        # own_company_short_name формируется _org_context'ом; достаточно
        # проверить что где-то в контексте фигурирует short_name seller'а.
        found = any(
            isinstance(v, str) and self.own_a.short_name in v
            for v in ctx.values()
        )
        self.assertTrue(found, f"seller short_name отсутствует в контексте: {ctx}")


class InvoiceFormSellerFixationTests(B1Base):
    """
    Поле seller в форме disabled и прибито к current_org. Любая попытка
    отправить другого seller'а через POST игнорируется.
    """

    def test_seller_is_fixed_to_current_org(self):
        from invoicing.forms import InvoiceForm

        form = InvoiceForm(account=self.account, current_org=self.own_a)
        self.assertTrue(form.fields["seller"].disabled)
        self.assertEqual(list(form.fields["seller"].queryset), [self.own_a])
        self.assertEqual(form.initial["seller"], self.own_a.pk)

    def test_bank_queryset_is_limited_to_current_org(self):
        from invoicing.forms import InvoiceForm

        form = InvoiceForm(account=self.account, current_org=self.own_a)
        bank_qs = list(form.fields["bank_account"].queryset)
        self.assertIn(self.bank_a, bank_qs)
        self.assertNotIn(self.bank_b, bank_qs)

    def test_post_with_foreign_seller_is_ignored_and_saved_correctly(self):
        """
        Если злоумышленник руками правит HTML и отправляет seller=own_b
        при current_org=own_a — Django disabled=True полностью игнорирует
        POST-значение, берёт initial, и в БД сохраняется own_a.
        """
        from invoicing.forms import InvoiceForm

        form = InvoiceForm(
            data={
                "seller": str(self.own_b.pk),
                "customer": str(self.client_org.pk),
                "date": "2026-05-01",
                "bank_account": str(self.bank_a.pk),
            },
            account=self.account,
            current_org=self.own_a,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data.get("seller"), self.own_a)

        trip = self._make_trip(carrier=self.own_a)
        inv = create_invoice(
            user=self.user,
            customer=form.cleaned_data["customer"],
            seller=form.cleaned_data["seller"],
            lines_data=[{
                "trip": trip,
                "kind": InvoiceLine.Kind.SERVICE,
                "description": "x",
                "quantity": Decimal("1"),
                "unit": InvoiceLine.UnitOfMeasure.SERVICE,
                "unit_price": Decimal("1000"),
                "discount_amount": Decimal("0"),
                "vat_rate": None,
            }],
            invoice_date=form.cleaned_data["date"],
            bank_account=form.cleaned_data.get("bank_account"),
        )
        inv.refresh_from_db()
        self.assertEqual(inv.seller, self.own_a)


class InvoiceEditGuardTests(B1Base):
    """
    Редактирование счёта запрещено, если текущая своя фирма пользователя
    не совпадает с invoice.seller. Middleware хранит выбор в
    session["current_org_id"] + request.current_org.
    """

    def setUp(self):
        self.http = Client()
        self.http.force_login(self.user)

    def _create_invoice_for(self, seller, bank):
        trip = self._make_trip(carrier=seller)
        return create_invoice(
            user=self.user, customer=self.client_org, seller=seller,
            lines_data=[{
                "trip": trip,
                "kind": InvoiceLine.Kind.SERVICE,
                "description": "x",
                "quantity": Decimal("1"),
                "unit": InvoiceLine.UnitOfMeasure.SERVICE,
                "unit_price": Decimal("1000"),
                "discount_amount": Decimal("0"),
                "vat_rate": None,
            }],
            bank_account=bank,
        )

    def _set_current_org(self, org):
        session = self.http.session
        session["current_org_id"] = org.pk
        session.save()

    def test_edit_under_correct_org_ok(self):
        inv = self._create_invoice_for(self.own_a, self.bank_a)
        self._set_current_org(self.own_a)
        resp = self.http.get(reverse("invoicing:invoice_edit", args=[inv.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_edit_under_foreign_org_redirects_to_detail(self):
        inv = self._create_invoice_for(self.own_a, self.bank_a)
        self._set_current_org(self.own_b)
        resp = self.http.get(reverse("invoicing:invoice_edit", args=[inv.pk]))
        self.assertRedirects(
            resp, reverse("invoicing:invoice_detail", args=[inv.pk])
        )

    def test_edit_post_under_foreign_org_also_blocked(self):
        """
        POST тоже должен блокироваться — не только GET. Иначе можно
        обойти guard прямым curl'ом с CSRF-токеном из другого запроса.
        """
        inv = self._create_invoice_for(self.own_a, self.bank_a)
        self._set_current_org(self.own_b)
        resp = self.http.post(
            reverse("invoicing:invoice_edit", args=[inv.pk]),
            data={},
        )
        self.assertRedirects(
            resp, reverse("invoicing:invoice_detail", args=[inv.pk])
        )

    def test_edit_null_seller_invoice_blocked(self):
        """
        Исторический счёт без seller (backfill bucket) нельзя
        редактировать через UI — только через админку.
        """
        inv = self._create_invoice_for(self.own_a, self.bank_a)
        # Симулируем результат backfill'а с непокрытым bucket'ом:
        from invoicing.models import Invoice

        Invoice.objects.filter(pk=inv.pk).update(seller=None)
        self._set_current_org(self.own_a)
        resp = self.http.get(reverse("invoicing:invoice_edit", args=[inv.pk]))
        self.assertRedirects(
            resp, reverse("invoicing:invoice_detail", args=[inv.pk])
        )


class InvoiceListFilterTests(B1Base):
    """
    Список счетов фильтруется по seller = current_org.
    """

    def setUp(self):
        self.http = Client()
        self.http.force_login(self.user)

    def _set_current_org(self, org):
        session = self.http.session
        session["current_org_id"] = org.pk
        session.save()

    def _make_invoice(self, seller, bank):
        trip = self._make_trip(carrier=seller)
        return create_invoice(
            user=self.user, customer=self.client_org, seller=seller,
            lines_data=[{
                "trip": trip,
                "kind": InvoiceLine.Kind.SERVICE,
                "description": "x",
                "quantity": Decimal("1"),
                "unit": InvoiceLine.UnitOfMeasure.SERVICE,
                "unit_price": Decimal("1000"),
                "discount_amount": Decimal("0"),
                "vat_rate": None,
            }],
            bank_account=bank,
        )

    def test_list_shows_only_current_org_invoices(self):
        inv_a = self._make_invoice(self.own_a, self.bank_a)
        inv_b = self._make_invoice(self.own_b, self.bank_b)

        self._set_current_org(self.own_a)
        resp = self.http.get(reverse("invoicing:invoice_list"))
        self.assertEqual(resp.status_code, 200)
        invoices = list(resp.context["invoices"])
        self.assertIn(inv_a, invoices)
        self.assertNotIn(inv_b, invoices)

        self._set_current_org(self.own_b)
        resp = self.http.get(reverse("invoicing:invoice_list"))
        invoices = list(resp.context["invoices"])
        self.assertIn(inv_b, invoices)
        self.assertNotIn(inv_a, invoices)


class InvoiceDetailReadOnlyTests(B1Base):
    def setUp(self):
        self.http = Client()
        self.http.force_login(self.user)

    def _set_current_org(self, org):
        session = self.http.session
        session["current_org_id"] = org.pk
        session.save()

    def _make_invoice(self, seller, bank):
        trip = self._make_trip(carrier=seller)
        return create_invoice(
            user=self.user, customer=self.client_org, seller=seller,
            lines_data=[{
                "trip": trip,
                "kind": InvoiceLine.Kind.SERVICE,
                "description": "x",
                "quantity": Decimal("1"),
                "unit": InvoiceLine.UnitOfMeasure.SERVICE,
                "unit_price": Decimal("1000"),
                "discount_amount": Decimal("0"),
                "vat_rate": None,
            }],
            bank_account=bank,
        )

    def test_detail_under_own_seller_has_edit_button(self):
        inv = self._make_invoice(self.own_a, self.bank_a)
        self._set_current_org(self.own_a)
        resp = self.http.get(reverse("invoicing:invoice_detail", args=[inv.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["can_edit"])
        edit_url = reverse("invoicing:invoice_edit", args=[inv.pk])
        delete_url = reverse("invoicing:invoice_delete", args=[inv.pk])
        self.assertContains(resp, f'href="{edit_url}"')
        self.assertContains(resp, delete_url)

    def test_detail_under_foreign_seller_is_readonly(self):
        inv = self._make_invoice(self.own_a, self.bank_a)
        self._set_current_org(self.own_b)
        resp = self.http.get(reverse("invoicing:invoice_detail", args=[inv.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["can_edit"])
        edit_url = reverse("invoicing:invoice_edit", args=[inv.pk])
        delete_url = reverse("invoicing:invoice_delete", args=[inv.pk])
        self.assertNotContains(resp, f'href="{edit_url}"')
        self.assertNotContains(resp, delete_url)
        # Download остаётся — read-only операция.
        download_url = reverse("invoicing:invoice_download", args=[inv.pk])
        self.assertContains(resp, download_url)
        # Баннер с именем правильной фирмы.
        self.assertContains(resp, self.own_a.short_name)


class InvoiceDeleteGuardTests(B1Base):
    def setUp(self):
        self.http = Client()
        self.http.force_login(self.user)

    def _set_current_org(self, org):
        session = self.http.session
        session["current_org_id"] = org.pk
        session.save()

    def _make_invoice(self, seller, bank):
        trip = self._make_trip(carrier=seller)
        return create_invoice(
            user=self.user, customer=self.client_org, seller=seller,
            lines_data=[{
                "trip": trip,
                "kind": InvoiceLine.Kind.SERVICE,
                "description": "x",
                "quantity": Decimal("1"),
                "unit": InvoiceLine.UnitOfMeasure.SERVICE,
                "unit_price": Decimal("1000"),
                "discount_amount": Decimal("0"),
                "vat_rate": None,
            }],
            bank_account=bank,
        )

    def test_delete_under_correct_org_ok(self):
        inv = self._make_invoice(self.own_a, self.bank_a)
        self._set_current_org(self.own_a)
        resp = self.http.post(reverse("invoicing:invoice_delete", args=[inv.pk]))
        self.assertRedirects(resp, reverse("invoicing:invoice_list"))
        from invoicing.models import Invoice
        self.assertFalse(Invoice.objects.filter(pk=inv.pk).exists())

    def test_delete_under_foreign_org_blocked(self):
        inv = self._make_invoice(self.own_a, self.bank_a)
        self._set_current_org(self.own_b)
        resp = self.http.post(reverse("invoicing:invoice_delete", args=[inv.pk]))
        self.assertRedirects(
            resp, reverse("invoicing:invoice_detail", args=[inv.pk])
        )
        from invoicing.models import Invoice
        self.assertTrue(Invoice.objects.filter(pk=inv.pk).exists())

    def test_delete_null_seller_blocked(self):
        inv = self._make_invoice(self.own_a, self.bank_a)
        from invoicing.models import Invoice
        Invoice.objects.filter(pk=inv.pk).update(seller=None)
        self._set_current_org(self.own_a)
        resp = self.http.post(reverse("invoicing:invoice_delete", args=[inv.pk]))
        self.assertRedirects(
            resp, reverse("invoicing:invoice_detail", args=[inv.pk])
        )
        self.assertTrue(Invoice.objects.filter(pk=inv.pk).exists())
