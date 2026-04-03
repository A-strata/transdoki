from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError, Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from billing.mixins import BillingProtectedMixin
from transdoki.tenancy import get_request_account
from transdoki.views import UserOwnedListView

from .forms import OrganizationForm
from .models import Bank, Organization, OrganizationBank, OrganizationContact
from .validators import validate_inn


class OrganizationCreateView(BillingProtectedMixin, LoginRequiredMixin, CreateView):
    model = Organization
    form_class = OrganizationForm
    template_name = "organizations/organization_form.html"
    success_url = reverse_lazy("organizations:list")

    def _is_own(self):
        return self.request.GET.get("own") == "1"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["force_is_own"] = self._is_own()
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.account = get_request_account(self.request)
        form.instance.is_own_company = self._is_own()

        try:
            return super().form_valid(form)
        except ValidationError as e:
            for field, errors in e.error_dict.items():
                for error in errors:
                    form.add_error(field, error)
            return self.form_invalid(form)
        except IntegrityError:
            form.add_error("inn", "Организация с таким ИНН уже существует.")
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_own"] = self._is_own()
        return context

    def get_success_url(self):
        return reverse("organizations:detail", kwargs={"pk": self.object.pk})


class OrganizationUpdateView(LoginRequiredMixin, UpdateView):
    model = Organization
    form_class = OrganizationForm
    template_name = "organizations/organization_form.html"

    def get_queryset(self):
        return Organization.objects.for_account(get_request_account(self.request))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["force_is_own"] = self.object.is_own_company
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_own"] = self.object.is_own_company
        context["back_url"] = self.request.GET.get("next", "")
        return context

    def form_valid(self, form):
        self._back_url = self.request.POST.get("back_url", "")
        return super().form_valid(form)

    def get_success_url(self):
        if self._back_url:
            return self._back_url
        return reverse("organizations:detail", kwargs={"pk": self.object.pk})


class OrganizationListMixin:
    """Поиск, сортировка и контекст для списков организаций."""

    model = Organization
    template_name = "organizations/organization_list.html"
    partial_template_name = "organizations/organization_list_table.html"
    context_object_name = "organizations"

    def get_template_names(self):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return [self.partial_template_name]
        return [self.template_name]

    def _parse_sort(self):
        sort_field = self.request.GET.get("sort", "short_name").strip()
        sort_dir = self.request.GET.get("dir", "asc").strip()
        if sort_field not in ("short_name", "inn"):
            sort_field = "short_name"
        if sort_dir not in ("asc", "desc"):
            sort_dir = "asc"
        return sort_field, sort_dir

    def _apply_search_and_sort(self, qs):
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(short_name__icontains=q) | Q(inn__icontains=q))
        sort_field, sort_dir = self._parse_sort()
        order = sort_field if sort_dir == "asc" else f"-{sort_field}"
        return qs.order_by(order)

    def _build_sort_url(self, field, current_sort, current_dir, q, page_size):
        params = {"sort": field}
        params["dir"] = (
            "desc" if (field == current_sort and current_dir == "asc") else "asc"
        )
        if q:
            params["q"] = q
        if str(page_size) != str(self.paginate_by):
            params["page_size"] = page_size
        return "?" + urlencode(params)

    def _get_org_list_context(self, context):
        page_obj = context.get("page_obj")
        context["pagination_items"] = (
            self._build_pagination_items(page_obj) if page_obj else []
        )
        context["page_size_options"] = self.page_size_options

        q = self.request.GET.get("q", "").strip()
        if q:
            context["total_count"] = (
                self.model.objects.for_account(
                    get_request_account(self.request),
                ).filter(
                    is_own_company=context.get("is_own", False),
                ).count()
            )
        sort_field, sort_dir = self._parse_sort()
        current_page_size = self.get_paginate_by(self.object_list)

        context["filters"] = {
            "q": q,
            "sort": sort_field,
            "dir": sort_dir,
            "page_size": str(current_page_size),
        }

        params = {}
        if q:
            params["q"] = q
        if sort_field != "short_name":
            params["sort"] = sort_field
        if sort_dir != "asc":
            params["dir"] = sort_dir
        if str(current_page_size) != str(self.paginate_by):
            params["page_size"] = current_page_size
        context["query_string"] = ("&" + urlencode(params)) if params else ""

        context["sort_urls"] = {
            "short_name": self._build_sort_url(
                "short_name", sort_field, sort_dir, q, current_page_size
            ),
            "inn": self._build_sort_url(
                "inn", sort_field, sort_dir, q, current_page_size
            ),
        }
        return context


class OrganizationListView(OrganizationListMixin, UserOwnedListView):
    def get_queryset(self):
        qs = super().get_queryset().filter(is_own_company=False)
        return self._apply_search_and_sort(qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_own"] = False
        return self._get_org_list_context(context)


class OwnCompanyListView(OrganizationListMixin, UserOwnedListView):
    def get_queryset(self):
        qs = super().get_queryset().filter(is_own_company=True)
        return self._apply_search_and_sort(qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_own"] = True
        return self._get_org_list_context(context)


class OrganizationDeleteView(LoginRequiredMixin, DeleteView):
    model = Organization
    template_name = "organizations/organization_confirm_delete.html"

    def get_queryset(self):
        return Organization.objects.for_account(get_request_account(self.request))

    def get_success_url(self):
        if self.object.is_own_company:
            return reverse("organizations:own_list")
        return reverse("organizations:list")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            self.object.delete()
            messages.success(request, f"Организация «{self.object.short_name}» удалена.")
            return redirect(self.get_success_url())
        except ProtectedError:
            messages.error(
                request,
                "Невозможно удалить: есть связанные рейсы, путевые листы или транспортные средства.",
            )
            return redirect(reverse("organizations:detail", kwargs={"pk": self.object.pk}))


class OrganizationDetailView(LoginRequiredMixin, DetailView):
    model = Organization
    template_name = "organizations/organization_detail.html"

    def get_queryset(self):
        return Organization.objects.for_account(get_request_account(self.request))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.object

        vehicles = org.vehicle_set.all()
        bank_accounts = org.bank_accounts.select_related("account_bank").all()
        contacts = org.contacts.all()

        ctx["vehicles"] = vehicles
        ctx["bank_accounts"] = bank_accounts
        ctx["contacts"] = contacts
        ctx["vehicles_count"] = vehicles.count()
        ctx["bank_accounts_count"] = bank_accounts.count()
        ctx["contacts_count"] = contacts.count()

        from trips.models import Trip
        from vehicles.models import PropertyType, VehicleType

        trips_qs = Trip.objects.for_account(org.account).prefetch_related("points")
        if org.is_own_company:
            ctx["recent_trips"] = (
                trips_qs.filter(carrier=org).order_by("-date_of_trip")[:5]
            )
        else:
            ctx["recent_trips"] = (
                trips_qs.filter(client=org).order_by("-date_of_trip")[:5]
            )

        ctx["vehicle_types"] = VehicleType.choices
        ctx["property_types"] = PropertyType.choices
        return ctx


@login_required
@require_GET
def organization_search(request):
    account = get_request_account(request)
    q = request.GET.get("q", "").strip()
    qs = Organization.objects.for_account(account)
    if request.GET.get("own") == "1":
        qs = qs.filter(is_own_company=True)
    if q:
        qs = qs.filter(short_name__icontains=q) | Organization.objects.for_account(
            account
        ).filter(inn__icontains=q)
    results = [
        {"id": o.pk, "text": o.short_name}
        for o in qs.order_by("short_name")[:25]
    ]
    return JsonResponse({"results": results})


@login_required
@require_POST
def organization_quick_create(request):
    account = get_request_account(request)
    inn = request.POST.get("inn", "").strip()
    full_name = request.POST.get("full_name", "").strip()
    short_name = request.POST.get("short_name", "").strip()

    errors = {}
    if not inn:
        errors["inn"] = "Обязательное поле"
    else:
        try:
            validate_inn(inn)
        except ValidationError as e:
            errors["inn"] = e.messages[0]
    if not full_name:
        errors["full_name"] = "Обязательное поле"
    if not short_name:
        errors["short_name"] = "Обязательное поле"

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    ogrn = request.POST.get("ogrn", "").strip() or None
    kpp = request.POST.get("kpp", "").strip() or None
    address = request.POST.get("address", "").strip() or None

    try:
        org = Organization(
            inn=inn,
            full_name=full_name,
            short_name=short_name,
            ogrn=ogrn,
            kpp=kpp,
            address=address,
            is_own_company=False,
            created_by=request.user,
            account=account,
        )
        org.save()
    except ValidationError as e:
        errs = {}
        if hasattr(e, "error_dict"):
            for field, msgs in e.error_dict.items():
                formatted = "; ".join(msgs[0].messages) if hasattr(msgs[0], "messages") else str(msgs[0])
                if field == "__all__":
                    errs["inn"] = "Организация с таким ИНН уже зарегистрирована в этом аккаунте"
                else:
                    errs[field] = formatted
        else:
            errs["inn"] = "; ".join(e.messages)
        return JsonResponse({"errors": errs}, status=400)
    except IntegrityError:
        return JsonResponse(
            {"errors": {"inn": "Организация с таким ИНН уже существует"}}, status=400
        )

    return JsonResponse({"id": org.pk, "text": org.short_name})


@login_required
@require_POST
def bank_account_quick_create(request):
    account = get_request_account(request)
    owner_id = request.POST.get("owner_id", "").strip()
    bic = request.POST.get("bic", "").strip()
    bank_name = request.POST.get("bank_name", "").strip()
    corr_account = request.POST.get("corr_account", "").strip()
    account_num = request.POST.get("account_num", "").strip()

    errors = {}
    if not bic:
        errors["bic"] = "Обязательное поле"
    elif not bic.isdigit() or len(bic) != 9:
        errors["bic"] = "БИК должен состоять из 9 цифр"
    if not bank_name:
        errors["bank_name"] = "Обязательное поле"
    if not corr_account:
        errors["corr_account"] = "Обязательное поле"
    elif not corr_account.isdigit() or len(corr_account) != 20:
        errors["corr_account"] = "Корр. счёт должен состоять из 20 цифр"
    if not account_num:
        errors["account_num"] = "Обязательное поле"
    elif not account_num.isdigit() or len(account_num) != 20:
        errors["account_num"] = "Расчётный счёт должен состоять из 20 цифр"

    org = None
    if owner_id:
        org = Organization.objects.for_account(account).filter(pk=owner_id).first()
    if not org:
        errors["owner_id"] = "Организация не найдена"

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    bank, _ = Bank.objects.get_or_create(
        bic=bic,
        defaults={"bank_name": bank_name, "corr_account": corr_account},
    )

    try:
        ob = OrganizationBank(
            account_num=account_num,
            account_owner=org,
            account_bank=bank,
            created_by=request.user,
            account=account,
        )
        ob.full_clean()
        ob.save()
    except ValidationError as e:
        errs = {}
        if hasattr(e, "error_dict"):
            for field, msgs in e.error_dict.items():
                msg = msgs[0].messages[0] if hasattr(msgs[0], "messages") else str(msgs[0])
                errs[field] = msg
        else:
            errs["account_num"] = "; ".join(e.messages)
        return JsonResponse({"errors": errs}, status=400)
    except IntegrityError:
        return JsonResponse(
            {"errors": {"account_num": "Такой счёт в этом банке уже существует"}},
            status=400,
        )

    return JsonResponse({"id": ob.pk, "text": f"{account_num} ({bank_name})"})


@login_required
@require_POST
def bank_account_update(request):
    account = get_request_account(request)
    ba_id = request.POST.get("ba_id", "").strip()
    account_num = request.POST.get("account_num", "").strip()
    bic = request.POST.get("bic", "").strip()
    bank_name = request.POST.get("bank_name", "").strip()
    corr_account = request.POST.get("corr_account", "").strip()

    ob = OrganizationBank.objects.for_account(account).filter(pk=ba_id).select_related("account_bank").first()
    if not ob:
        return JsonResponse({"errors": {"ba_id": "Счёт не найден"}}, status=404)

    errors = {}
    if not bic:
        errors["bic"] = "Обязательное поле"
    elif not bic.isdigit() or len(bic) != 9:
        errors["bic"] = "БИК должен состоять из 9 цифр"
    if not bank_name:
        errors["bank_name"] = "Обязательное поле"
    if not corr_account:
        errors["corr_account"] = "Обязательное поле"
    elif not corr_account.isdigit() or len(corr_account) != 20:
        errors["corr_account"] = "Корр. счёт должен состоять из 20 цифр"
    if not account_num:
        errors["account_num"] = "Обязательное поле"
    elif not account_num.isdigit() or len(account_num) != 20:
        errors["account_num"] = "Расчётный счёт должен состоять из 20 цифр"

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    bank, _ = Bank.objects.get_or_create(
        bic=bic,
        defaults={"bank_name": bank_name, "corr_account": corr_account},
    )

    ob.account_num = account_num
    ob.account_bank = bank
    try:
        ob.full_clean()
        ob.save()
    except ValidationError as e:
        errs = {}
        if hasattr(e, "error_dict"):
            for field, msgs in e.error_dict.items():
                msg = msgs[0].messages[0] if hasattr(msgs[0], "messages") else str(msgs[0])
                errs[field] = msg
        else:
            errs["account_num"] = "; ".join(e.messages)
        return JsonResponse({"errors": errs}, status=400)
    except IntegrityError:
        return JsonResponse(
            {"errors": {"account_num": "Такой счёт в этом банке уже существует"}},
            status=400,
        )

    return JsonResponse({"ok": True})


@login_required
@require_POST
def bank_account_delete(request):
    account = get_request_account(request)
    ba_id = request.POST.get("ba_id", "").strip()

    ob = OrganizationBank.objects.for_account(account).filter(pk=ba_id).first()
    if not ob:
        return JsonResponse({"error": "Счёт не найден"}, status=404)

    ob.delete()
    return JsonResponse({"ok": True})


def _clean_phone(phone):
    """Нормализация и валидация российского номера. Возвращает (digits, error)."""
    if not phone:
        return "", None
    digits = "".join(filter(str.isdigit, phone))
    if not digits or digits == "7":
        return "", None
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if len(digits) != 11 or not digits.startswith("7"):
        return phone, "Введите корректный российский номер телефона"
    return digits, None


@login_required
@require_POST
def contact_quick_create(request):
    account = get_request_account(request)
    org_id = request.POST.get("org_id", "").strip()
    name = request.POST.get("name", "").strip()
    phone = request.POST.get("phone", "").strip()
    position = request.POST.get("position", "").strip()

    errors = {}
    if not name:
        errors["name"] = "Обязательное поле"

    org = None
    if org_id:
        org = Organization.objects.for_account(account).filter(pk=org_id).first()
    if not org:
        errors["org_id"] = "Организация не найдена"

    phone, phone_error = _clean_phone(phone)
    if phone_error:
        errors["phone"] = phone_error

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    contact = OrganizationContact.objects.create(
        organization=org,
        name=name,
        phone=phone,
        position=position,
        created_by=request.user,
        account=account,
    )

    return JsonResponse({"id": contact.pk, "text": str(contact)})


@login_required
@require_POST
def contact_update(request):
    account = get_request_account(request)
    contact_id = request.POST.get("contact_id", "").strip()
    name = request.POST.get("name", "").strip()
    phone = request.POST.get("phone", "").strip()
    position = request.POST.get("position", "").strip()

    contact = OrganizationContact.objects.filter(
        pk=contact_id, account=account,
    ).first()
    if not contact:
        return JsonResponse({"errors": {"contact_id": "Контакт не найден"}}, status=404)

    errors = {}
    if not name:
        errors["name"] = "Обязательное поле"

    phone, phone_error = _clean_phone(phone)
    if phone_error:
        errors["phone"] = phone_error

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    contact.name = name
    contact.phone = phone
    contact.position = position
    contact.save()

    return JsonResponse({"ok": True})


@login_required
@require_POST
def contact_delete(request):
    account = get_request_account(request)
    contact_id = request.POST.get("contact_id", "").strip()

    contact = OrganizationContact.objects.filter(
        pk=contact_id, account=account,
    ).first()

    if not contact:
        return JsonResponse({"error": "Контакт не найден"}, status=404)

    contact.delete()
    return JsonResponse({"ok": True})
