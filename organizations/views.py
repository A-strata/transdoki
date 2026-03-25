from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from transdoki.tenancy import get_request_account

from billing.mixins import BillingProtectedMixin

from .forms import OrganizationForm
from .models import Organization
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

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.account = get_request_account(self.request)

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

    def get_success_url(self):
        return reverse("organizations:detail", kwargs={"pk": self.object.pk})


class OrganizationUpdateView(LoginRequiredMixin, UpdateView):
    model = Organization
    form_class = OrganizationForm
    template_name = "organizations/organization_form.html"

    def get_queryset(self):
        return Organization.objects.filter(account=get_request_account(self.request))

    def form_valid(self, form):
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("organizations:detail", kwargs={"pk": self.object.pk})


class OrganizationListView(UserOwnedListView):
    model = Organization
    template_name = "organizations/organization_list.html"
    context_object_name = "organizations"


class OrganizationDetailView(LoginRequiredMixin, DetailView):
    model = Organization
    template_name = "organizations/organization_detail.html"

    def get_queryset(self):
        return Organization.objects.filter(account=get_request_account(self.request))


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
