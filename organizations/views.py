from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from transdoki.tenancy import get_request_account

from billing.mixins import BillingProtectedMixin

from .forms import OrganizationForm
from .models import Bank, Organization, OrganizationBank
from .validators import validate_inn


class UserOwnedListView(LoginRequiredMixin, ListView):
    """Базовый View показывающий только записи текущего account (tenant)."""

    def get_queryset(self):
        return self.model.objects.filter(account=get_request_account(self.request))


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
        return Organization.objects.filter(account=get_request_account(self.request))

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


class OrganizationListView(UserOwnedListView):
    model = Organization
    template_name = "organizations/organization_list.html"
    context_object_name = "organizations"

    def get_queryset(self):
        return super().get_queryset().filter(is_own_company=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_own"] = False
        return context


class OwnCompanyListView(UserOwnedListView):
    model = Organization
    template_name = "organizations/organization_list.html"
    context_object_name = "organizations"

    def get_queryset(self):
        return super().get_queryset().filter(is_own_company=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_own"] = True
        return context


class OrganizationDeleteView(LoginRequiredMixin, DeleteView):
    model = Organization
    template_name = "organizations/organization_confirm_delete.html"

    def get_queryset(self):
        return Organization.objects.filter(account=get_request_account(self.request))

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
        return Organization.objects.filter(account=get_request_account(self.request))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.object

        vehicles = org.vehicle_set.all()
        bank_accounts = org.bank_accounts.select_related("account_bank").all()
        employees = org.employees.all()

        ctx["vehicles"] = vehicles
        ctx["bank_accounts"] = bank_accounts
        ctx["employees"] = employees
        ctx["vehicles_count"] = vehicles.count()
        ctx["bank_accounts_count"] = bank_accounts.count()
        ctx["employees_count"] = employees.count()

        from trips.models import Trip
        from vehicles.models import PropertyType, VehicleType

        trips_qs = Trip.objects.filter(account=org.account).prefetch_related("points")
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
    qs = Organization.objects.filter(account=account)
    if request.GET.get("own") == "1":
        qs = qs.filter(is_own_company=True)
    if q:
        qs = qs.filter(short_name__icontains=q) | Organization.objects.filter(
            account=account, inn__icontains=q
        )
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
        org = Organization.objects.filter(pk=owner_id, account=account).first()
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
