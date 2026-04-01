import json
import logging
import os

import requests
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.forms.models import model_to_dict
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.decorators.http import require_GET
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from dotenv import load_dotenv

from transdoki.tenancy import get_request_account

from vehicles.models import PropertyType, VehicleType

from .forms import TripAttachmentUploadForm, TripForm, TripPointForm
from .models import MAX_FILES_PER_TRIP, FinancialStatus, Trip, TripAttachment, TripPoint
from .services import AgreementRequestGenerator, TNGenerator

load_dotenv()
DADATA_TOKEN = os.getenv("DADATA_TOKEN")
DADATA_SECRET = os.getenv("DADATA_SECRET")
DADATA_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"

logger = logging.getLogger("security")



class UserOwnedListView(LoginRequiredMixin, ListView):
    """Базовый View показывающий только записи пользователя"""

    def get_queryset(self):
        return self.model.objects.filter(account=get_request_account(self.request))


class RoutePointsMixin:
    """Миксин для работы с мультиточечным маршрутом в формах создания/редактирования рейса."""

    DEFAULT_POINTS = [
        {"point_type": "LOAD", "address": "", "planned_date": "", "organization": "",
         "organization_name": "", "loading_type": "", "contact_name": "", "contact_phone": ""},
        {"point_type": "UNLOAD", "address": "", "planned_date": "", "organization": "",
         "organization_name": "", "loading_type": "", "contact_name": "", "contact_phone": ""},
    ]

    def _points_from_db(self, trip):
        """Сериализует точки из БД в список dict для JSON."""
        points = []
        for p in trip.points.select_related("organization").all():
            points.append({
                "id": p.pk,
                "point_type": p.point_type,
                "address": p.address,
                "planned_date": p.planned_date.strftime("%Y-%m-%dT%H:%M") if p.planned_date else "",
                "organization": p.organization_id or "",
                "organization_name": str(p.organization) if p.organization else "",
                "loading_type": p.loading_type,
                "contact_name": p.contact_name,
                "contact_phone": p.contact_phone,
            })
        return points

    def _points_from_post(self, post_data):
        """Парсит points_json из POST."""
        raw = post_data.get("points_json", "[]")
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []

    def _validate_points(self, points_data, user):
        """Валидирует каждую точку через TripPointForm. Возвращает (forms, is_valid, global_errors)."""
        forms = []
        all_valid = True
        global_errors = []

        if not points_data:
            global_errors.append("Необходимо добавить хотя бы одну точку погрузки и одну точку выгрузки.")
            return forms, False, global_errors

        has_load = any(p.get("point_type") == "LOAD" for p in points_data)
        has_unload = any(p.get("point_type") == "UNLOAD" for p in points_data)
        if not has_load or not has_unload:
            global_errors.append("Маршрут должен содержать минимум одну точку погрузки и одну точку выгрузки.")

        for pt in points_data:
            form = TripPointForm(data=pt, user=user)
            if not form.is_valid():
                all_valid = False
            forms.append(form)

        if global_errors:
            all_valid = False

        return forms, all_valid, global_errors

    def _enrich_points_with_errors(self, points_data, point_forms):
        """Добавляет ошибки валидации к данным точек для передачи в шаблон."""
        enriched = []
        for pt_data, form in zip(points_data, point_forms):
            entry = dict(pt_data)
            if form.errors:
                entry["errors"] = {
                    field: [str(e) for e in errs]
                    for field, errs in form.errors.items()
                }
            enriched.append(entry)
        return enriched

    @transaction.atomic
    def _save_points(self, trip, point_forms, points_data):
        """Сохраняет точки маршрута и синхронизирует Trip.consignor/consignee."""
        # Удаляем старые точки
        trip.points.all().delete()

        saved_points = []
        for seq, (form, pt_data) in enumerate(zip(point_forms, points_data), start=1):
            point = form.save(commit=False)
            point.trip = trip
            point.sequence = seq
            point.save()
            saved_points.append(point)

        # Обратная совместимость: заполняем Trip.consignor / Trip.consignee
        consignor = None
        consignee = None
        for p in saved_points:
            if p.point_type == TripPoint.Type.LOAD and consignor is None:
                consignor = p.organization
            elif p.point_type == TripPoint.Type.UNLOAD and consignee is None:
                consignee = p.organization

        trip.consignor = consignor
        trip.consignee = consignee
        trip.save(update_fields=["consignor", "consignee"])


class TripCreateView(RoutePointsMixin, LoginRequiredMixin, CreateView):
    model = Trip
    form_class = TripForm
    template_name = "trips/trip_form.html"

    COPY_EXCLUDE_FIELDS = {
        "created_by", "account", "created_at", "updated_at",
        "num_of_trip", "date_of_trip",
        "weight", "volume", "client_cost", "carrier_cost", "comments",
        "client_quantity", "carrier_quantity",
        "client_financial_status", "client_total_fixed",
        "carrier_financial_status", "carrier_total_fixed",
    }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["vehicle_types"] = VehicleType.choices
        ctx["property_types"] = PropertyType.choices
        org = getattr(self.request, "current_org", None)
        if org:
            ctx["role_org"] = {
                "id": org.id,
                "name": str(org),
                "has_vehicles": org.vehicle_set.exists(),
            }
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def _get_copy_source(self):
        copy_from_id = self.request.GET.get("copy_from")
        if not copy_from_id:
            return None
        account = get_request_account(self.request)
        return Trip.objects.filter(
            pk=copy_from_id, account=account
        ).prefetch_related("points", "points__organization").first()

    def get_initial(self):
        initial = super().get_initial()
        source = self._get_copy_source()
        if not source:
            return initial
        form_fields = set(self.form_class.base_fields.keys())
        fields_to_copy = [f for f in form_fields if f not in self.COPY_EXCLUDE_FIELDS]
        initial.update(model_to_dict(source, fields=fields_to_copy))
        return initial

    def _get_initial_points(self):
        source = self._get_copy_source()
        if source:
            return self._points_from_db(source)
        return list(self.DEFAULT_POINTS)

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        points_data = self._get_initial_points()
        return self.render_to_response(
            self.get_context_data(form=form, points_json=json.dumps(points_data, ensure_ascii=False))
        )

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        points_data = self._points_from_post(request.POST)
        point_forms, points_valid, points_errors = self._validate_points(points_data, request.user)

        if form.is_valid() and points_valid:
            form.instance.created_by = request.user
            form.instance.account = get_request_account(request)
            self.object = form.save()
            self._save_points(self.object, point_forms, points_data)
            return redirect(self.get_success_url())

        enriched = self._enrich_points_with_errors(points_data, point_forms) if point_forms else points_data
        return self.render_to_response(
            self.get_context_data(
                form=form,
                points_json=json.dumps(enriched, ensure_ascii=False),
                points_errors=points_errors,
            )
        )

    def get_success_url(self):
        return reverse_lazy("trips:detail", kwargs={"pk": self.object.pk})


class TripUpdateView(RoutePointsMixin, LoginRequiredMixin, UpdateView):
    model = Trip
    form_class = TripForm
    template_name = "trips/trip_form.html"

    def get_queryset(self):
        return Trip.objects.filter(
            account=get_request_account(self.request)
        ).prefetch_related("points", "points__organization")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["vehicle_types"] = VehicleType.choices
        ctx["property_types"] = PropertyType.choices
        org = getattr(self.request, "current_org", None)
        if org:
            ctx["role_org"] = {
                "id": org.id,
                "name": str(org),
                "has_vehicles": org.vehicle_set.exists(),
            }
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        points_data = self._points_from_db(self.object)
        return self.render_to_response(
            self.get_context_data(form=form, points_json=json.dumps(points_data, ensure_ascii=False))
        )

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        points_data = self._points_from_post(request.POST)
        point_forms, points_valid, points_errors = self._validate_points(points_data, request.user)

        if form.is_valid() and points_valid:
            self.object = form.save()
            self._save_points(self.object, point_forms, points_data)
            return redirect(self.get_success_url())

        enriched = self._enrich_points_with_errors(points_data, point_forms) if point_forms else points_data
        return self.render_to_response(
            self.get_context_data(
                form=form,
                points_json=json.dumps(enriched, ensure_ascii=False),
                points_errors=points_errors,
            )
        )

    def get_success_url(self):
        return reverse_lazy("trips:detail", kwargs={"pk": self.object.pk})


class TripDetailView(LoginRequiredMixin, DetailView):
    model = Trip
    template_name = "trips/trip_detail.html"

    def get_queryset(self):
        return Trip.objects.filter(
            account=get_request_account(self.request)
        ).prefetch_related("attachments", "points", "points__organization")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["attachment_form"] = TripAttachmentUploadForm()
        context["max_files_per_trip"] = MAX_FILES_PER_TRIP

        trip = self.object
        client_total = trip.client_total
        carrier_total = trip.carrier_total
        if client_total is not None and carrier_total is not None:
            context["margin"] = client_total - carrier_total
            if client_total:
                context["margin_percent"] = round(
                    (client_total - carrier_total) / client_total * 100
                )
        context["route_summary"] = self._build_route_summary(trip)

        # Определение роли пользователя в рейсе
        org = getattr(self.request, "current_org", None)
        if org:
            if trip.client_id == org.id:
                context["trip_role"] = "client"
            elif trip.carrier_id == org.id:
                context["trip_role"] = "carrier"
            else:
                context["trip_role"] = "forwarder"

        return context

    @staticmethod
    def _build_route_summary(trip):
        points = list(trip.points.all())
        if not points:
            return ""
        cities = []
        for p in points:
            if p.address:
                city = p.address.split(",")[0].strip()
                if not cities or cities[-1] != city:
                    cities.append(city)
        return " → ".join(cities) if cities else ""


class TripListView(UserOwnedListView):
    model = Trip
    template_name = "trips/trip_list.html"
    context_object_name = "trips"
    paginate_by = 25
    page_size_options = [2, 25, 50, 100]

    date_mode_options = [
        ("loading", "Погрузка"),
        ("unloading", "Выгрузка"),
    ]

    contractor_role_options = [
        ("client", "Заказчик"),
        ("carrier", "Перевозчик"),
        ("consignor", "Отправитель (погрузка)"),
        ("consignee", "Получатель (выгрузка)"),
        ("driver", "Водитель"),
    ]

    def get_paginate_by(self, queryset):
        raw_value = (self.request.GET.get("page_size") or "").strip()

        if raw_value.isdigit():
            value = int(raw_value)
            if value in self.page_size_options:
                return value

        return self.paginate_by

    def get_page_number(self):
        raw_page = (self.request.GET.get("page") or "").strip()
        if raw_page.isdigit() and int(raw_page) > 0:
            return int(raw_page)
        return 1

    def _normalize_date_value(self, value):
        value = (value or "").strip()
        return value or None

    def _apply_date_filters(self, qs):
        date_mode = (self.request.GET.get("date_mode") or "loading").strip()
        date_from = self._normalize_date_value(self.request.GET.get("date_from"))
        date_to = self._normalize_date_value(self.request.GET.get("date_to"))

        if not date_from and not date_to:
            return qs

        sequence = 1 if date_mode != "unloading" else 2
        filter_kwargs = {"points__sequence": sequence}
        if date_from:
            filter_kwargs["points__planned_date__date__gte"] = date_from
        if date_to:
            filter_kwargs["points__planned_date__date__lte"] = date_to

        return qs.filter(**filter_kwargs).distinct()



    def _apply_contractor_filter(self, qs):
        contractor_role = (self.request.GET.get("contractor_role") or "").strip()
        contractor_query = (self.request.GET.get("contractor_query") or "").strip()

        if not contractor_role or not contractor_query:
            return qs

        if contractor_role in ["client", "carrier"]:
            return qs.filter(
                **{f"{contractor_role}__short_name__icontains": contractor_query}
            )

        if contractor_role == "consignor":
            return qs.filter(
                points__point_type="LOAD",
                points__organization__short_name__icontains=contractor_query,
            ).distinct()

        if contractor_role == "consignee":
            return qs.filter(
                points__point_type="UNLOAD",
                points__organization__short_name__icontains=contractor_query,
            ).distinct()

        if contractor_role == "driver":
            parts = [part for part in contractor_query.split() if part]

            for part in parts:
                qs = (
                    qs.filter(driver__surname__icontains=part)
                    | qs.filter(driver__name__icontains=part)
                    | qs.filter(driver__patronymic__icontains=part)
                )

            return qs.distinct()

        return qs

    def _has_active_filters(self):
        date_from = (self.request.GET.get("date_from") or "").strip()
        date_to = (self.request.GET.get("date_to") or "").strip()
        contractor_role = (self.request.GET.get("contractor_role") or "").strip()
        contractor_query = (self.request.GET.get("contractor_query") or "").strip()
        date_mode = (self.request.GET.get("date_mode") or "").strip()

        if date_from or date_to or contractor_role or contractor_query:
            return True

        if date_mode and date_mode != "loading":
            return True

        return False

    def _should_open_last_page_by_default(self):
        page = (self.request.GET.get("page") or "").strip()
        if page:
            return False

        if self._has_active_filters():
            return False

        return True

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related(
                "client",
                "carrier",
                "driver",
                "truck",
                "trailer",
            )
            .prefetch_related("points", "points__organization")
        )

        current_org = getattr(self.request, "current_org", None)
        if current_org:
            qs = qs.filter(Q(client=current_org) | Q(carrier=current_org))

        qs = self._apply_date_filters(qs)
        qs = self._apply_contractor_filter(qs)

        return qs.order_by("date_of_trip", "pk")

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

    def _get_adjusted_page_for_page_size(self):
        old_page_size_raw = (self.request.GET.get("current_page_size") or "").strip()
        new_page_size = self.get_paginate_by(None)
        current_page = self.get_page_number()

        if old_page_size_raw.isdigit():
            old_page_size = int(old_page_size_raw)
            if old_page_size > 0:
                offset = (current_page - 1) * old_page_size
                return (offset // new_page_size) + 1

        return current_page

    def paginate_queryset(self, queryset, page_size):
        adjusted_page = self._get_adjusted_page_for_page_size()

        if self._should_open_last_page_by_default():
            paginator = Paginator(queryset, page_size)
            adjusted_page = paginator.num_pages or 1

        mutable_get = self.request.GET.copy()
        mutable_get["page"] = str(adjusted_page)
        self.request.GET = mutable_get

        return super().paginate_queryset(queryset, page_size)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        current_page_size = self.get_paginate_by(self.object_list)

        context["page_size_options"] = self.page_size_options
        context["date_mode_options"] = self.date_mode_options
        context["contractor_role_options"] = self.contractor_role_options

        context["filters"] = {
            "date_mode": (self.request.GET.get("date_mode") or "loading").strip(),
            "date_from": (self.request.GET.get("date_from") or "").strip(),
            "date_to": (self.request.GET.get("date_to") or "").strip(),
            "contractor_role": (self.request.GET.get("contractor_role") or "").strip(),
            "contractor_query": (
                self.request.GET.get("contractor_query") or ""
            ).strip(),
            "page_size": str(current_page_size),
        }

        page_obj = context.get("page_obj")
        context["pagination_items"] = (
            self._build_pagination_items(page_obj) if page_obj else []
        )

        return context


class TripTNDownloadView(LoginRequiredMixin, View):
    def get(self, request, pk):
        trip = get_object_or_404(Trip, pk=pk, account=get_request_account(request))
        return TNGenerator.generate_response(trip)


class TripAgreementDownloadView(LoginRequiredMixin, View):
    def get(self, request, pk):
        trip = get_object_or_404(Trip, pk=pk, account=get_request_account(request))
        return AgreementRequestGenerator.generate_response(trip)


@login_required
@require_GET
def trip_search(request):
    account = get_request_account(request)
    q = (request.GET.get("q") or "").strip()
    qs = Trip.objects.filter(account=account).order_by("-date_of_trip", "-num_of_trip")
    if q:
        qs = qs.filter(num_of_trip__icontains=q)
    results = [
        {
            "id": t.pk,
            "text": f"№{t.num_of_trip} от {t.date_of_trip.strftime('%d.%m.%Y')}",
        }
        for t in qs[:25]
    ]
    return JsonResponse({"results": results})


@login_required
@require_GET
def address_suggest(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 3:
        return JsonResponse({"suggestions": []})

    headers = {
        "Authorization": f"Token {DADATA_TOKEN}",
        "X-Secret": DADATA_SECRET,
        "Content-Type": "application/json",
    }
    payload = {
        "query": q,
        "count": 5,  # максимум 5 вариантов
    }

    try:
        resp = requests.post(DADATA_URL, json=payload, headers=headers, timeout=3)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return JsonResponse({"suggestions": []})

    result = [{"value": s.get("value", "")} for s in data.get("suggestions", [])]
    return JsonResponse({"suggestions": result})


class TripAttachmentUploadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        trip = get_object_or_404(Trip, pk=pk, account=get_request_account(request))
        form = TripAttachmentUploadForm(request.POST, request.FILES)

        if not form.is_valid():
            messages.error(
                request, "Не удалось загрузить файлы. Проверьте выбранные файлы."
            )
            return redirect("trips:detail", pk=trip.pk)

        files = form.cleaned_data["files"]
        existing_count = trip.attachments.count()
        free_slots = MAX_FILES_PER_TRIP - existing_count

        if len(files) > free_slots:
            messages.error(
                request,
                f"Можно загрузить ещё только {free_slots} файл(ов). Максимум: {MAX_FILES_PER_TRIP}.",
            )
            return redirect("trips:detail", pk=trip.pk)

        try:
            with transaction.atomic():
                for uploaded_file in files:
                    TripAttachment.objects.create(
                        trip=trip,
                        created_by=request.user,
                        account=trip.account,
                        file=uploaded_file,
                        original_name=uploaded_file.name,
                        file_size=uploaded_file.size,
                    )
        except ValidationError as exc:
            messages.error(request, f"Ошибка валидации файла: {exc}")
            return redirect("trips:detail", pk=trip.pk)

        messages.success(request, "Файлы успешно загружены.")
        return redirect("trips:detail", pk=trip.pk)


class TripAttachmentDownloadView(LoginRequiredMixin, View):
    def get(self, request, pk, attachment_pk):
        attachment = get_object_or_404(
            TripAttachment.objects.select_related("trip"),
            pk=attachment_pk,
            trip_id=pk,
            trip__account=get_request_account(request),
        )
        return FileResponse(
            attachment.file.open("rb"),
            as_attachment=True,
            filename=attachment.original_name,
        )


class TripFixFinancialView(LoginRequiredMixin, View):
    """Фиксирует итоговую сумму для одной стороны (client/carrier)."""

    def post(self, request, pk):
        detail_finances_url = reverse("trips:detail", args=[pk]) + "#finances"
        side = request.POST.get("side")
        if side not in ("client", "carrier"):
            messages.error(request, "Неверный параметр.")
            return redirect(detail_finances_url)

        trip = get_object_or_404(Trip, pk=pk, account=get_request_account(request))

        current_status = (
            trip.client_financial_status
            if side == "client"
            else trip.carrier_financial_status
        )
        if current_status != FinancialStatus.OPEN:
            messages.error(request, "Сумма уже зафиксирована.")
            return redirect(detail_finances_url)

        total = trip.client_total if side == "client" else trip.carrier_total
        if total is None:
            messages.error(
                request,
                "Невозможно рассчитать итог: заполните ставку"
                + (" и фактическое количество." if side == "client" else " и фактическое количество."),
            )
            return redirect(detail_finances_url)

        if side == "client":
            trip.client_total_fixed = total
            trip.client_financial_status = FinancialStatus.CALCULATED
            update_fields = ["client_total_fixed", "client_financial_status"]
            label = "заказчика"
        else:
            trip.carrier_total_fixed = total
            trip.carrier_financial_status = FinancialStatus.CALCULATED
            update_fields = ["carrier_total_fixed", "carrier_financial_status"]
            label = "перевозчика"

        trip.save(update_fields=update_fields)
        messages.success(
            request, f"Сумма {label} зафиксирована: {total:,.2f} ₽".replace(",", "\u00a0")
        )
        return redirect(detail_finances_url)


class TripAttachmentDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, attachment_pk):
        attachment = get_object_or_404(
            TripAttachment.objects.select_related("trip"),
            pk=attachment_pk,
            trip_id=pk,
            trip__account=get_request_account(request),
        )
        attachment.delete()
        messages.success(request, "Файл удалён.")
        return redirect("trips:detail", pk=pk)
