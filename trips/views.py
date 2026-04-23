import json
import logging
import os
from urllib.parse import urlencode

import requests
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Subquery
from django.forms.models import model_to_dict
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.decorators.http import require_GET
from django.views.generic import CreateView, DetailView, UpdateView
from dotenv import load_dotenv

from billing.mixins import LimitCheckMixin
from billing.services.limits import can_create_trip
from transdoki.tenancy import get_request_account
from transdoki.views import UserOwnedListView

from organizations.models import Organization
from vehicles.models import PropertyType, VehicleType

from .forms import TripAttachmentUploadForm, TripForm, TripPointForm
from .models import MAX_FILES_PER_TRIP, Trip, TripAttachment, TripPoint
from .services import AgreementRequestGenerator, TNGenerator

load_dotenv()
DADATA_TOKEN = os.getenv("DADATA_TOKEN")
DADATA_SECRET = os.getenv("DADATA_SECRET")
DADATA_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"

logger = logging.getLogger("security")


class RoutePointsMixin:
    """Миксин для работы с мультиточечным маршрутом в формах создания/редактирования рейса."""

    DEFAULT_POINTS = [
        {"point_type": "LOAD", "address": "", "planned_date": "", "planned_time": "",
         "organization": "", "organization_name": "", "loading_type": "",
         "contact_name": "", "contact_phone": ""},
        {"point_type": "UNLOAD", "address": "", "planned_date": "", "planned_time": "",
         "organization": "", "organization_name": "", "loading_type": "",
         "contact_name": "", "contact_phone": ""},
    ]

    def _points_from_db(self, trip):
        """Сериализует точки из БД в список dict для JSON."""
        points = []
        for p in trip.points.select_related("organization").all():
            points.append({
                "id": p.pk,
                "point_type": p.point_type,
                "address": p.address,
                "planned_date": p.planned_date.strftime("%Y-%m-%d") if p.planned_date else "",
                "planned_time": p.planned_time.strftime("%H:%M") if p.planned_time else "",
                "organization": p.organization_id or "",
                "organization_name": str(p.organization) if p.organization else "",
                "loading_type": p.loading_type,
                "contact_name": p.contact_name,
                "contact_phone": p.contact_phone,
            })
        return points

    def _points_from_post(self, post_data, account=None):
        """Парсит points_json из POST и обогащает точки именем организации
        из БД (в пределах account). Имя, пришедшее с клиента, игнорируется —
        клиент не источник истины, это защита от рассинхрона и IDOR."""
        raw = post_data.get("points_json", "[]")
        try:
            points = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(points, list):
            return []

        if account is not None:
            from organizations.models import Organization

            ids = {
                p["organization"]
                for p in points
                if isinstance(p, dict) and p.get("organization")
            }
            names = {}
            if ids:
                names = dict(
                    Organization.objects.for_account(account)
                    .filter(pk__in=ids)
                    .values_list("pk", "short_name")
                )
            for p in points:
                if not isinstance(p, dict):
                    continue
                org_id = p.get("organization")
                try:
                    org_pk = int(org_id) if org_id not in (None, "") else None
                except (TypeError, ValueError):
                    org_pk = None
                p["organization_name"] = names.get(org_pk, "") if org_pk else ""
        return points

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
        """Сохраняет точки маршрута."""
        # Удаляем старые точки
        trip.points.all().delete()

        for seq, (form, pt_data) in enumerate(zip(point_forms, points_data), start=1):
            point = form.save(commit=False)
            point.trip = trip
            point.sequence = seq
            point.save()


class TripCreateView(LimitCheckMixin, RoutePointsMixin, LoginRequiredMixin, CreateView):
    model = Trip
    form_class = TripForm
    template_name = "trips/trip_form.html"
    # Блокирует создание при past_due/suspended/cancelled подписке.
    # Лимит рейсов мягкий (overage начисляется в charge_monthly) —
    # can_create_trip не проверяет число рейсов в текущем периоде.
    limit_check_callable = staticmethod(can_create_trip)

    COPY_EXCLUDE_FIELDS = {
        "created_by", "account", "created_at", "updated_at",
        "num_of_trip", "date_of_trip",
        "weight", "volume", "client_cost", "carrier_cost", "comments",
        "client_quantity", "carrier_quantity",
        "client_financial_status", "client_total_fixed",
        "carrier_financial_status", "carrier_total_fixed",
        "forwarder",
    }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["vehicle_types"] = VehicleType.choices
        ctx["property_types"] = PropertyType.choices
        org = getattr(self.request, "current_org", None)
        if org:
            own_org_ids = list(
                Organization.objects.own_for(
                    get_request_account(self.request)
                ).values_list("pk", flat=True)
            )
            ctx["role_org"] = {
                "id": org.id,
                "name": str(org),
                "has_vehicles": org.vehicle_set.exists(),
                # Список pk всех «моих» фирм account-а. Нужен JS-у для Phase 2
                # (фильтрация дропдаунов по роли: forwarder → client/carrier из
                # чужих; client/carrier own → второй участник тоже может быть own
                # для internal-рейса). Сейчас передаём на будущее — data-атрибут
                # создаётся в шаблоне, но Phase 1 JS его не читает.
                "own_org_ids": own_org_ids,
            }
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["current_org"] = getattr(self.request, "current_org", None)
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
        if source:
            form_fields = set(self.form_class.base_fields.keys())
            fields_to_copy = [f for f in form_fields if f not in self.COPY_EXCLUDE_FIELDS]
            initial.update(model_to_dict(source, fields=fields_to_copy))
            return initial

        # Без copy_from: предзаполняем client или carrier текущей навбар-фирмой.
        # Правило: has_vehicles → carrier, иначе → client.
        org = getattr(self.request, "current_org", None)
        if org:
            field = "carrier" if org.vehicle_set.exists() else "client"
            initial.setdefault(field, org.pk)
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
        points_data = self._points_from_post(request.POST, account=get_request_account(request))
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
        return Trip.objects.for_account(
            get_request_account(self.request)
        ).prefetch_related("points", "points__organization")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["vehicle_types"] = VehicleType.choices
        ctx["property_types"] = PropertyType.choices
        org = getattr(self.request, "current_org", None)
        if org:
            own_org_ids = list(
                Organization.objects.own_for(
                    get_request_account(self.request)
                ).values_list("pk", flat=True)
            )
            ctx["role_org"] = {
                "id": org.id,
                "name": str(org),
                "has_vehicles": org.vehicle_set.exists(),
                "own_org_ids": own_org_ids,
            }
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["current_org"] = getattr(self.request, "current_org", None)
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
        points_data = self._points_from_post(request.POST, account=get_request_account(request))
        point_forms, points_valid, points_errors = self._validate_points(points_data, request.user)

        if form.is_valid() and points_valid:
            form.instance.updated_by = request.user
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
        return Trip.objects.for_account(
            get_request_account(self.request)
        ).select_related("client", "carrier", "forwarder").prefetch_related(
            "attachments", "points", "points__organization"
        )

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

        # Роль текущей фирмы через perspective()
        org = getattr(self.request, "current_org", None)
        perspective = trip.perspective(org)
        context["perspective"] = perspective
        context["trip_role"] = perspective["role"] if org else None

        context["invoice_block"] = self._build_invoice_block(
            trip, org, context["trip_role"]
        )

        return context

    @staticmethod
    def _build_invoice_block(trip, current_org, trip_role):
        """
        Возвращает dict для рендера секции «Счёт на оплату» в карточке рейса.

        Состояния:
            hidden   — блок не рендерится (пользователь — заказчик или
                       не участвует; нет активной фирмы);
            issued   — счёт уже выставлен, показать ссылку и сумму;
            blocked  — выставить нельзя, объяснить причину + предложить
                       действие (заполнить данные / добавить р/с);
            ready    — всё готово к выставлению счёта.

        Порядок проверок для blocked:
            1) Наличный расчёт — счёт не нужен;
            2) Не указана сумма заказчику — нельзя сформировать строку;
            3) У seller-фирмы нет расчётного счёта — нельзя сформировать
               платёжные реквизиты.
        """
        # Блок скрыт: нет активной своей фирмы, или роль не "исполнитель".
        if current_org is None or trip_role not in ("carrier", "forwarder"):
            return {"state": "hidden"}

        # Уже выставлен — показать ссылку на счёт.
        invoice_line = (
            trip.invoice_lines
            .select_related("invoice")
            .order_by("invoice__year", "invoice__number")
            .first()
        )
        if invoice_line is not None:
            invoice = invoice_line.invoice
            return {
                "state": "issued",
                "invoice": invoice,
                "invoice_line_pk": invoice_line.pk,
            }

        # Наличный расчёт с заказчиком — счёт не выставляется.
        if trip.client_payment_method == "cash":
            return {
                "state": "blocked",
                "reason": "Наличный расчёт с заказчиком — счёт не требуется.",
            }

        # Нет суммы клиенту — нечего выставлять.
        if trip.client_total is None:
            return {
                "state": "blocked",
                "reason": "Не указана стоимость для заказчика.",
                "reason_link": {
                    "url": reverse("trips:edit", kwargs={"pk": trip.pk}),
                    "text": "Заполнить",
                },
            }

        # Нет расчётного счёта у нашей фирмы — нечего подставить в реквизиты.
        if not current_org.bank_accounts.exists():
            return {
                "state": "blocked",
                "reason": (
                    f"У фирмы «{current_org.short_name}» нет расчётного счёта."
                ),
                "reason_link": {
                    "url": reverse(
                        "organizations:edit", kwargs={"pk": current_org.pk}
                    ),
                    "text": "Добавить",
                },
            }

        return {"state": "ready"}

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
    partial_template_name = "trips/trip_list_tbody.html"
    context_object_name = "trips"
    paginate_by = 25
    page_size_options = [25, 50, 100]

    def get_template_names(self):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return [self.partial_template_name]
        return [self.template_name]

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
            filter_kwargs["points__planned_date__gte"] = date_from
        if date_to:
            filter_kwargs["points__planned_date__lte"] = date_to

        return qs.filter(**filter_kwargs).distinct()



    CONTRACTOR_ROLES = ("client", "carrier", "driver", "truck", "trailer")

    def _get_contractor_filters(self):
        result = {}
        for role in self.CONTRACTOR_ROLES:
            val = (self.request.GET.get(f"contractor_{role}") or "").strip()
            if val:
                result[role] = val
        return result

    def _apply_contractor_filter(self, qs):
        filters = self._get_contractor_filters()

        for role, query in filters.items():
            if role in ("client", "carrier"):
                qs = qs.filter(
                    **{f"{role}__short_name__icontains": query}
                )
            elif role == "driver":
                parts = [part for part in query.split() if part]
                for part in parts:
                    qs = (
                        qs.filter(driver__surname__icontains=part)
                        | qs.filter(driver__name__icontains=part)
                        | qs.filter(driver__patronymic__icontains=part)
                    )
                qs = qs.distinct()
            elif role in ("truck", "trailer"):
                qs = qs.filter(**{f"{role}__grn__icontains": query})

        return qs

    def _has_active_filters(self):
        date_from = (self.request.GET.get("date_from") or "").strip()
        date_to = (self.request.GET.get("date_to") or "").strip()
        date_mode = (self.request.GET.get("date_mode") or "").strip()

        if date_from or date_to:
            return True

        if date_mode and date_mode != "loading":
            return True

        if self._get_contractor_filters():
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
                "forwarder",
                "driver",
                "truck",
                "trailer",
            )
            .prefetch_related("points", "points__organization")
        )

        current_org = getattr(self.request, "current_org", None)
        if current_org:
            qs = qs.filter(
                Q(client=current_org)
                | Q(carrier=current_org)
                | Q(forwarder=current_org)
            )

        from invoicing.models import InvoiceLine

        active_lines = InvoiceLine.objects.filter(trip=OuterRef("pk"))
        qs = qs.annotate(
            invoice_pk=Subquery(active_lines.values("invoice_id")[:1]),
            invoice_number=Subquery(active_lines.values("invoice__number")[:1]),
        )

        qs = self._apply_search(qs)
        qs = self._apply_date_filters(qs)
        qs = self._apply_contractor_filter(qs)

        return qs.order_by("date_of_trip", "pk")

    def _apply_search(self, qs):
        q = (self.request.GET.get("q") or "").strip()
        if not q:
            return qs
        point_match = TripPoint.objects.filter(
            trip=OuterRef("pk"),
            organization__short_name__icontains=q,
        )
        return qs.filter(
            Q(num_of_trip__icontains=q)
            | Q(client__short_name__icontains=q)
            | Q(carrier__short_name__icontains=q)
            | Q(forwarder__short_name__icontains=q)
            | Exists(point_match)
        )

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

    def paginate_queryset(self, queryset, page_size):
        if self._should_open_last_page_by_default():
            paginator = Paginator(queryset, page_size)
            adjusted_page = paginator.num_pages or 1
            mutable_get = self.request.GET.copy()
            mutable_get["page"] = str(adjusted_page)
            self.request.GET = mutable_get

        return super().paginate_queryset(queryset, page_size)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        current_org = getattr(self.request, "current_org", None)
        for trip in context.get("trips", []):
            trip.my_perspective = trip.perspective(current_org)

        current_page_size = self.get_paginate_by(self.object_list)

        context["page_size_options"] = self.page_size_options
        context["date_mode_options"] = self.date_mode_options
        context["contractor_role_options"] = self.contractor_role_options

        contractor_filters = self._get_contractor_filters()

        context["filters"] = {
            "q": (self.request.GET.get("q") or "").strip(),
            "date_mode": (self.request.GET.get("date_mode") or "loading").strip(),
            "date_from": (self.request.GET.get("date_from") or "").strip(),
            "date_to": (self.request.GET.get("date_to") or "").strip(),
            "contractors": contractor_filters,
            "page_size": str(current_page_size),
        }

        page_obj = context.get("page_obj")
        context["pagination_items"] = (
            self._build_pagination_items(page_obj) if page_obj else []
        )

        base_params = {}
        if context["filters"]["q"]:
            base_params["q"] = context["filters"]["q"]
        if context["filters"]["date_mode"] != "loading":
            base_params["date_mode"] = context["filters"]["date_mode"]
        if context["filters"]["date_from"]:
            base_params["date_from"] = context["filters"]["date_from"]
        if context["filters"]["date_to"]:
            base_params["date_to"] = context["filters"]["date_to"]
        for role, query in contractor_filters.items():
            base_params[f"contractor_{role}"] = query
        if str(current_page_size) != str(self.paginate_by):
            base_params["page_size"] = current_page_size
        context["query_string"] = ("&" + urlencode(base_params)) if base_params else ""

        return context


class TripTNDownloadView(LoginRequiredMixin, View):
    def get(self, request, pk):
        trip = get_object_or_404(
            Trip.objects.select_related("carrier", "client", "driver"),
            pk=pk,
            account=get_request_account(request),
        )
        return TNGenerator.generate_response(trip)


class TripAgreementDownloadView(LoginRequiredMixin, View):
    def get(self, request, pk):
        trip = get_object_or_404(
            Trip.objects.select_related("carrier", "client", "driver").prefetch_related(
                "carrier__bank_accounts__account_bank",
                "client__bank_accounts__account_bank",
            ),
            pk=pk,
            account=get_request_account(request),
        )
        return AgreementRequestGenerator.generate_response(trip)


@login_required
@require_GET
def trip_search(request):
    account = get_request_account(request)
    q = (request.GET.get("q") or "").strip()
    qs = Trip.objects.for_account(account).order_by("-date_of_trip", "-num_of_trip")
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

        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        if not form.is_valid():
            if is_ajax:
                return JsonResponse(
                    {"ok": False, "error": "Не удалось загрузить файлы. Проверьте выбранные файлы."},
                    status=400,
                )
            messages.error(
                request, "Не удалось загрузить файлы. Проверьте выбранные файлы."
            )
            return redirect("trips:detail", pk=trip.pk)

        files = form.cleaned_data["files"]
        existing_count = trip.attachments.count()
        free_slots = MAX_FILES_PER_TRIP - existing_count

        if len(files) > free_slots:
            error_msg = f"Можно загрузить ещё только {free_slots} файл(ов). Максимум: {MAX_FILES_PER_TRIP}."
            if is_ajax:
                return JsonResponse({"ok": False, "error": error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect("trips:detail", pk=trip.pk)

        try:
            created = []
            with transaction.atomic():
                for uploaded_file in files:
                    att = TripAttachment.objects.create(
                        trip=trip,
                        created_by=request.user,
                        account=trip.account,
                        file=uploaded_file,
                        original_name=uploaded_file.name,
                        file_size=uploaded_file.size,
                    )
                    created.append(att)
        except ValidationError as exc:
            if is_ajax:
                return JsonResponse({"ok": False, "error": str(exc)}, status=400)
            messages.error(request, f"Ошибка валидации файла: {exc}")
            return redirect("trips:detail", pk=trip.pk)

        if is_ajax:
            return JsonResponse({
                "ok": True,
                "attachments": [
                    {
                        "pk": att.pk,
                        "original_name": att.original_name,
                        "created_at": att.created_at.strftime("%d.%m.%Y %H:%M"),
                        "download_url": reverse(
                            "trips:attachment_download",
                            args=[pk, att.pk],
                        ),
                        "delete_url": reverse(
                            "trips:attachment_delete",
                            args=[pk, att.pk],
                        ),
                    }
                    for att in created
                ],
            })
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


class TripAttachmentDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, attachment_pk):
        attachment = get_object_or_404(
            TripAttachment.objects.select_related("trip"),
            pk=attachment_pk,
            trip_id=pk,
            trip__account=get_request_account(request),
        )
        attachment.delete()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": True})
        messages.success(request, "Файл удалён.")
        return redirect("trips:detail", pk=pk)
