from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView

from organizations.models import Organization
from transdoki.tenancy import get_request_account

from billing.mixins import BillingProtectedMixin

from .forms import VehicleForm
from .models import Vehicle, VehicleType


class UserOwnedListView(LoginRequiredMixin, ListView):
    """Базовый View показывающий только записи текущего account (tenant)."""

    def get_queryset(self):
        return self.model.objects.filter(account=get_request_account(self.request))


class VehicleCreateView(BillingProtectedMixin, LoginRequiredMixin, CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = "vehicles/vehicle_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["organization_pk"] = self.kwargs["organization_pk"]
        return context

    def get_success_url(self):
        return reverse(
            "organizations:detail", kwargs={"pk": self.kwargs["organization_pk"]}
        )

    def form_valid(self, form):
        account = get_request_account(self.request)

        owner = Organization.objects.filter(
            pk=self.kwargs["organization_pk"],
            account=account,
        ).first()
        if owner is None:
            raise PermissionDenied("Организация недоступна в текущем account.")

        form.instance.created_by = self.request.user
        form.instance.account = account
        form.instance.owner = owner

        try:
            return super().form_valid(form)
        except IntegrityError:
            form.add_error("grn", "ТС с таким номером уже существует.")
            return self.form_invalid(form)


class VehicleUpdateView(LoginRequiredMixin, UpdateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = "vehicles/vehicle_form.html"

    def get_queryset(self):
        return Vehicle.objects.filter(account=get_request_account(self.request))

    def get_success_url(self):
        return reverse("organizations:detail", kwargs={"pk": self.object.owner.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["organization_pk"] = self.object.owner.pk
        return context

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except IntegrityError:
            form.add_error("grn", "ТС с таким номером уже существует.")
            return self.form_invalid(form)


class VehicleListView(UserOwnedListView):
    model = Vehicle
    template_name = "vehicles/vehicle_list.html"
    context_object_name = "vehicles"


@login_required
@require_POST
def vehicle_quick_create(request):
    account = get_request_account(request)
    grn = request.POST.get("grn", "").strip().upper()
    brand = request.POST.get("brand", "").strip()
    model = request.POST.get("model", "").strip()
    vehicle_type = request.POST.get("vehicle_type", "").strip()
    owner_id = request.POST.get("owner_id", "").strip()

    property_type = request.POST.get("property_type", "").strip()

    valid_vehicle_types = [t[0] for t in VehicleType.choices]
    valid_property_types = [t[0] for t in Vehicle.property_type.field.choices]
    errors = {}
    if not grn:
        errors["grn"] = "Обязательное поле"
    if not brand:
        errors["brand"] = "Обязательное поле"
    if vehicle_type not in valid_vehicle_types:
        errors["vehicle_type"] = "Выберите тип ТС"
    if property_type not in valid_property_types:
        errors["property_type"] = "Выберите тип владения"
    if not owner_id:
        errors["owner_id"] = "Выберите владельца"

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    owner = Organization.objects.filter(pk=owner_id, account=account).first()
    if owner is None:
        return JsonResponse(
            {"errors": {"owner_id": "Организация не найдена"}}, status=400
        )

    try:
        vehicle = Vehicle(
            grn=grn,
            brand=brand,
            model=model,
            vehicle_type=vehicle_type,
            property_type=property_type,
            owner=owner,
            created_by=request.user,
            account=account,
        )
        vehicle.save()
    except IntegrityError:
        return JsonResponse(
            {"errors": {"grn": "ТС с таким номером уже существует"}}, status=400
        )

    return JsonResponse({"id": vehicle.pk, "text": str(vehicle)})
