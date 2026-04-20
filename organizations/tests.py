"""
Regression-тесты для OrganizationCreateView.

Сценарий «лимит своих компаний исчерпан» раньше редиректил на
organizations:list — это страница «Контрагентов» (фильтр
is_own_company=False), параметр ?own=1 она не принимает. Пользователь
из ЛК жал «+ Добавить компанию» и оказывался в контрагентах.

Hotfix: при лимите redirect уходит на Referer (если есть) или на
organizations:own_list — фолбэк, осмысленный для own-контекста.
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import Account
from organizations.models import Organization

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["*"])
class OrganizationCreateLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="own-limit", password="x")
        self.account = Account.objects.create(name="Acc", owner=self.user)
        self.user.profile.account = self.account
        self.user.profile.save(update_fields=["account"])
        # Free-план по миграции 0005: лимит 1 своя компания.
        # Создаём одну — дальнейшее создание должно блокироваться.
        Organization.objects.create(
            account=self.account,
            full_name="My LLC",
            short_name="My",
            inn="7707083893",
            is_own_company=True,
        )
        self.client = Client()
        self.client.force_login(self.user)

    def _create_url(self):
        return reverse("organizations:create") + "?own=1"

    def test_limit_reached_redirects_to_referer(self):
        """Из ЛК (Referer=cabinet) должны вернуться в ЛК, не в контрагенты."""
        cabinet = "http://testserver" + reverse("accounts:cabinet")
        resp = self.client.get(self._create_url(), HTTP_REFERER=cabinet)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, cabinet)

    def test_limit_reached_without_referer_falls_back_to_own_list(self):
        """Без Referer фолбэк — список собственных компаний, не контрагентов."""
        resp = self.client.get(self._create_url())
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("organizations:own_list"))
        # Проверяем, что это НЕ вкладка контрагентов.
        self.assertNotEqual(resp.url, reverse("organizations:list"))

    def test_counterparty_creation_not_limited(self):
        """Контрагенты (без ?own=1) — справочник, лимит не применяется."""
        resp = self.client.get(reverse("organizations:create"))
        self.assertEqual(resp.status_code, 200)


@override_settings(ALLOWED_HOSTS=["*"])
class OrganizationListContextTests(TestCase):
    """
    Бриф organizations-limit-parity v1.0 §1, §9: контекст списка отдаёт
    can_create_own_org / org_limit / org_count_current, UI по ним
    строит primary-CTA «+ Добавить компанию» или fallback «Увеличить лимит →».
    """

    def setUp(self):
        self.user = User.objects.create_user(username="ctx-user", password="x")
        self.account = Account.objects.create(name="CtxAcc", owner=self.user)
        self.user.profile.account = self.account
        self.user.profile.save(update_fields=["account"])
        self.client = Client()
        self.client.force_login(self.user)

    def test_own_list_under_limit_allows_create(self):
        """org_count < org_limit → can_create_own_org=True, кнопка primary видна."""
        # Free-план: лимит 1, ни одной своей пока не создано.
        resp = self.client.get(reverse("organizations:own_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["can_create_own_org"])
        self.assertEqual(resp.context["org_count_current"], 0)
        self.assertEqual(resp.context["org_limit"], 1)
        content = resp.content.decode()
        self.assertIn("+ Добавить компанию", content)
        self.assertNotIn("Увеличить лимит", content)

    def test_own_list_at_limit_shows_upgrade_cta(self):
        """org_count == org_limit → can_create_own_org=False, CTA апгрейда."""
        Organization.objects.create(
            account=self.account,
            full_name="Existing LLC",
            short_name="Ex",
            inn="7707083893",
            is_own_company=True,
        )
        resp = self.client.get(reverse("organizations:own_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["can_create_own_org"])
        self.assertEqual(resp.context["org_count_current"], 1)
        content = resp.content.decode()
        self.assertIn("Увеличить лимит", content)
        # primary-кнопка «+ Добавить компанию» заменена, её нет.
        self.assertNotIn("+ Добавить компанию", content)

    def test_counterparty_list_ignores_own_limit(self):
        """На контрагентах «+ Добавить контрагента» виден всегда.

        Лимит своих компаний исчерпан — но это влияет только на сайдбар
        (org-dropdown) и страницу own-list. Тулбар на /organizations/
        (контрагенты) рендерит primary-CTA «+ Добавить контрагента».
        """
        Organization.objects.create(
            account=self.account,
            full_name="Own LLC",
            short_name="Own",
            inn="7728168971",
            is_own_company=True,
        )
        resp = self.client.get(reverse("organizations:list"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn("+ Добавить контрагента", content)

    def test_exempt_account_always_allowed(self):
        """is_billing_exempt — CTA примари доступна независимо от счётчика."""
        self.account.is_billing_exempt = True
        self.account.save(update_fields=["is_billing_exempt"])
        Organization.objects.create(
            account=self.account,
            full_name="Exempt LLC",
            short_name="Ex",
            inn="7743013901",
            is_own_company=True,
        )
        resp = self.client.get(reverse("organizations:own_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["can_create_own_org"])
        self.assertIn("+ Добавить компанию", resp.content.decode())
