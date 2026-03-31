from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.db.models import ProtectedError, Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from billing.mixins import BillingProtectedMixin
from organizations.models import Organization
from transdoki.tenancy import get_request_account

from .forms import VehicleForm, VehicleFormWithOwner
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
        next_url = self.request.GET.get("next", "")
        return next_url or reverse("vehicles:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["back_url"] = self.request.GET.get("next", "") or reverse("vehicles:list")
        return context

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except IntegrityError:
            form.add_error("grn", "ТС с таким номером уже существует.")
            return self.form_invalid(form)


class VehicleDetailView(LoginRequiredMixin, DetailView):
    model = Vehicle
    template_name = "vehicles/vehicle_detail.html"

    def get_queryset(self):
        return Vehicle.objects.filter(account=get_request_account(self.request))


class VehicleCreateStandaloneView(BillingProtectedMixin, LoginRequiredMixin, CreateView):
    """Создание ТС со страницы списка (с выбором собственника в форме)."""

    model = Vehicle
    form_class = VehicleFormWithOwner
    template_name = "vehicles/vehicle_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['account'] = get_request_account(self.request)
        return kwargs

    def get_success_url(self):
        if self.request.POST.get("add_another"):
            return reverse("vehicles:create")
        return reverse("vehicles:list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.account = get_request_account(self.request)
        try:
            response = super().form_valid(form)
        except IntegrityError:
            form.add_error("grn", "ТС с таким номером уже существует.")
            return self.form_invalid(form)
        messages.success(self.request, f"ТС «{self.object}» добавлено.")
        return response


class VehicleDeleteView(LoginRequiredMixin, DeleteView):
    model = Vehicle
    template_name = "vehicles/vehicle_confirm_delete.html"

    def get_queryset(self):
        return Vehicle.objects.filter(account=get_request_account(self.request))

    def get_success_url(self):
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        if next_url:
            return next_url
        return reverse("vehicles:list")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        owner_pk = self.object.owner_id
        try:
            self.object.delete()
            messages.success(request, f"ТС «{self.object}» удалено.")
            return redirect(self.get_success_url())
        except ProtectedError:
            messages.error(
                request,
                "Невозможно удалить: есть связанные рейсы или путевые листы.",
            )
            next_url = request.POST.get("next") or request.GET.get("next")
            if next_url:
                return redirect(next_url)
            return redirect(reverse("vehicles:list"))


class VehicleListView(LoginRequiredMixin, ListView):
    model = Vehicle
    template_name = "vehicles/vehicle_list.html"
    partial_template_name = "vehicles/vehicle_list_table.html"
    context_object_name = "vehicles"
    paginate_by = 25
    page_size_options = [25, 50, 100]

    def get_template_names(self):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return [self.partial_template_name]
        return [self.template_name]

    def get_paginate_by(self, queryset):
        raw = (self.request.GET.get("page_size") or "").strip()
        if raw.isdigit():
            value = int(raw)
            if value in self.page_size_options:
                return value
        return self.paginate_by

    def get_queryset(self):
        current_org = self.request.current_org
        if current_org is None:
            return Vehicle.objects.none()

        qs = Vehicle.objects.filter(owner=current_org).select_related("owner")

        type_filter = self.request.GET.get("type", "all")
        valid_types = {vt[0] for vt in VehicleType.choices}
        if type_filter in valid_types:
            qs = qs.filter(vehicle_type=type_filter)

        return qs

    def _build_pagination_items(self, page_obj):
        current = page_obj.number
        total = page_obj.paginator.num_pages

        if total <= 7:
            return [
                {"type": "page", "number": n, "current": n == current}
                for n in range(1, total + 1)
            ]

        pages = {1, total, current - 2, current - 1, current, current + 1, current + 2}
        pages = sorted(n for n in pages if 1 <= n <= total)

        items = []
        prev = None

        for n in pages:
            if prev is not None and n - prev > 1:
                items.append({"type": "ellipsis"})
            items.append({"type": "page", "number": n, "current": n == current})
            prev = n

        return items

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_type = self.request.GET.get("type", "all")
        context["current_type"] = current_type
        context["vehicle_types"] = VehicleType.choices

        page_obj = context.get("page_obj")
        context["pagination_items"] = (
            self._build_pagination_items(page_obj) if page_obj else []
        )
        context["page_size_options"] = self.page_size_options

        current_page_size = self.get_paginate_by(self.object_list)
        context["filters"] = {
            "type": current_type,
            "page_size": str(current_page_size),
        }

        params = {}
        if current_type != "all":
            params["type"] = current_type
        if str(current_page_size) != str(self.paginate_by):
            params["page_size"] = current_page_size
        context["query_string"] = ("&" + urlencode(params)) if params else ""

        return context


@login_required
@require_GET
def vehicle_search(request):
    account = get_request_account(request)
    q = request.GET.get("q", "").strip()
    vtype = request.GET.get("type", "")
    qs = Vehicle.objects.filter(account=account)
    if request.GET.get("own") == "1":
        qs = qs.filter(owner__is_own_company=True)
    carrier_id = request.GET.get("carrier_id", "").strip()
    if carrier_id.isdigit():
        qs = qs.filter(owner_id=int(carrier_id))
    if vtype == "truck":
        qs = qs.filter(vehicle_type__in=["truck", "single"])
    elif vtype == "trailer":
        qs = qs.filter(vehicle_type="trailer")
    if q:
        qs = qs.filter(Q(grn__icontains=q) | Q(brand__icontains=q))
    results = [
        {"id": v.pk, "text": str(v)}
        for v in qs.order_by("grn")[:25]
    ]
    return JsonResponse({"results": results})


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
