import logging
import os

import requests
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.forms.models import model_to_dict
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.decorators.http import require_GET
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from dotenv import load_dotenv

from transdoki.tenancy import get_request_account

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


class TripCreateView(LoginRequiredMixin, CreateView):
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
        ).prefetch_related("points").first()

    def get_initial(self):
        initial = super().get_initial()
        source = self._get_copy_source()
        if not source:
            return initial
        form_fields = set(self.form_class.base_fields.keys())
        fields_to_copy = [f for f in form_fields if f not in self.COPY_EXCLUDE_FIELDS]
        initial.update(model_to_dict(source, fields=fields_to_copy))
        return initial

    def _point_initials_from_copy(self):
        source = self._get_copy_source()
        if not source:
            return {}, {}
        load_p = source.load_point
        unload_p = source.unload_point
        load_initial = (
            {"address": load_p.address, "loading_type": load_p.loading_type}
            if load_p else {}
        )
        unload_initial = (
            {"address": unload_p.address, "loading_type": unload_p.loading_type}
            if unload_p else {}
        )
        return load_initial, unload_initial

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        load_initial, unload_initial = self._point_initials_from_copy()
        load_form = TripPointForm(prefix="load", initial=load_initial)
        unload_form = TripPointForm(prefix="unload", initial=unload_initial)
        return self.render_to_response(
            self.get_context_data(form=form, load_form=load_form, unload_form=unload_form)
        )

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        load_form = TripPointForm(request.POST, prefix="load")
        unload_form = TripPointForm(request.POST, prefix="unload")
        if form.is_valid() and load_form.is_valid() and unload_form.is_valid():
            return self._save_all(form, load_form, unload_form)
        return self.render_to_response(
            self.get_context_data(form=form, load_form=load_form, unload_form=unload_form)
        )

    def _save_all(self, form, load_form, unload_form):
        form.instance.created_by = self.request.user
        form.instance.account = get_request_account(self.request)
        self.object = form.save()
        load_p = load_form.save(commit=False)
        load_p.trip = self.object
        load_p.point_type = TripPoint.Type.LOAD
        load_p.sequence = 1
        load_p.save()
        unload_p = unload_form.save(commit=False)
        unload_p.trip = self.object
        unload_p.point_type = TripPoint.Type.UNLOAD
        unload_p.sequence = 2
        unload_p.save()
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy("trips:detail", kwargs={"pk": self.object.pk})


class TripUpdateView(LoginRequiredMixin, UpdateView):
    model = Trip
    form_class = TripForm
    template_name = "trips/trip_form.html"

    def get_queryset(self):
        return Trip.objects.filter(
            account=get_request_account(self.request)
        ).prefetch_related("points")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        load_form = TripPointForm(instance=self.object.load_point, prefix="load")
        unload_form = TripPointForm(instance=self.object.unload_point, prefix="unload")
        return self.render_to_response(
            self.get_context_data(form=form, load_form=load_form, unload_form=unload_form)
        )

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        load_form = TripPointForm(
            request.POST, instance=self.object.load_point, prefix="load"
        )
        unload_form = TripPointForm(
            request.POST, instance=self.object.unload_point, prefix="unload"
        )
        if form.is_valid() and load_form.is_valid() and unload_form.is_valid():
            return self._save_all(form, load_form, unload_form)
        return self.render_to_response(
            self.get_context_data(form=form, load_form=load_form, unload_form=unload_form)
        )

    def _save_all(self, form, load_form, unload_form):
        self.object = form.save()
        load_p = load_form.save(commit=False)
        load_p.trip = self.object
        load_p.point_type = TripPoint.Type.LOAD
        load_p.sequence = 1
        load_p.save()
        unload_p = unload_form.save(commit=False)
        unload_p.trip = self.object
        unload_p.point_type = TripPoint.Type.UNLOAD
        unload_p.sequence = 2
        unload_p.save()
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy("trips:detail", kwargs={"pk": self.object.pk})


class TripDetailView(LoginRequiredMixin, DetailView):
    model = Trip
    template_name = "trips/trip_detail.html"

    def get_queryset(self):
        return Trip.objects.filter(
            account=get_request_account(self.request)
        ).prefetch_related("attachments", "points")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["attachment_form"] = TripAttachmentUploadForm()
        context["max_files_per_trip"] = MAX_FILES_PER_TRIP
        return context


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
        ("consignor", "Отправитель"),
        ("consignee", "Получатель"),
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

        if contractor_role in ["client", "carrier", "consignor", "consignee"]:
            return qs.filter(
                **{f"{contractor_role}__short_name__icontains": contractor_query}
            )

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
                "consignor",
                "consignee",
                "driver",
                "truck",
                "trailer",
            )
            .prefetch_related("points")
        )

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
