import logging
import os

import requests
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.decorators.http import require_GET
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from dotenv import load_dotenv

from .forms import TripForm
from .models import Trip
from .services import TNGenerator

load_dotenv()
DADATA_TOKEN = os.getenv('DADATA_TOKEN')
DADATA_SECRET = os.getenv('DADATA_SECRET')
DADATA_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"

logger = logging.getLogger('security')


class UserOwnedListView(LoginRequiredMixin, ListView):
    """Базовый View показывающий только записи пользователя"""
    def get_queryset(self):
        return self.model.objects.filter(created_by=self.request.user)


class TripCreateView0(LoginRequiredMixin, CreateView):
    model = Trip
    form_class = TripForm
    template_name = 'trips/trip_form.html'
    success_url = reverse_lazy('trips:list')

    def get_form_kwargs(self):
        # Готовит контекст для формы
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user  # Передает user для фильтрации
        return kwargs

    def form_valid(self, form):
        # Управляет созданием объекта
        form.instance.created_by = self.request.user  # Устанавливает создателя
        return super().form_valid(form)  # Делегирует сохранение


class TripCreateView(LoginRequiredMixin, CreateView):
    model = Trip
    form_class = TripForm
    template_name = 'trips/trip_form.html'
    success_url = reverse_lazy('trips:list')

    # Поля, которые НЕ копируем
    COPY_EXCLUDE_FIELDS = {
        'created_by',
        'created_at',
        'updated_at',
        'num_of_trip',
        'date_of_trip',
        'planned_loading_date',
        'planned_unloading_date',
        'actual_loading_date',
        'actual_unloading_date',
        'weight',
        'client_cost',
        'carrier_cost',
        'comments',
    }

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        copy_from_id = self.request.GET.get('copy_from')
        if not copy_from_id:
            return initial

        # Чтобы пользователь не мог копировать чужие рейсы
        source_trip = Trip.objects.filter(
            pk=copy_from_id,
            created_by=self.request.user
        ).first()
        if not source_trip:
            return initial

        # Копируем только поля, которые реально есть в форме
        form_fields = set(self.form_class.base_fields.keys())
        fields_to_copy = [
            f for f in form_fields if f not in self.COPY_EXCLUDE_FIELDS
        ]

        initial.update(model_to_dict(source_trip, fields=fields_to_copy))
        return initial

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class TripUpdateView(LoginRequiredMixin, UpdateView):
    model = Trip
    form_class = TripForm
    template_name = 'trips/trip_form.html'
    success_url = reverse_lazy('trips:list')

    def get_queryset(self):
        # Ограничивает доступ только к своим рейсам
        return Trip.objects.filter(created_by=self.request.user)

    def get_form_kwargs(self):
        # Готовит контекст для формы
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user  # Передает user для фильтрации
        return kwargs

    def form_valid(self, form):
        # Управляет обновлением объекта (created_by уже установлен)
        return super().form_valid(form)  # Делегирует сохранение


class TripDetailView(LoginRequiredMixin, DetailView):
    model = Trip
    template_name = 'trips/trip_detail.html'


class TripListView(UserOwnedListView):
    model = Trip
    template_name = 'trips/trip_list.html'
    context_object_name = 'trips'  # опционально, для ясности в шаблоне


def print_tn(request, pk):
    """View для генерации ТН"""
    trip = get_object_or_404(Trip, id=pk)
    file_path = TNGenerator.generate_tn(trip)

    if trip.created_by != request.user:

        logger.warning(
            f"Unauthorized TN access attempt: "
            f"user={request.user.username}({request.user.id}) "
            f"tried to access trip={trip.id} "
            f"owned by user={trip.created_by.username}({trip.created_by.id}) "
            f"IP={request.META.get('REMOTE_ADDR')}"
        )

        raise PermissionDenied(
            "У вас нет доступа к этой транспортной накладной"
        )

    file_path = TNGenerator.generate_tn(trip)
    return TNGenerator.create_file_response(file_path, trip)


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
        resp = requests.post(
            DADATA_URL, json=payload, headers=headers, timeout=3
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return JsonResponse({"suggestions": []})

    result = [
        {"value": s.get("value", "")} for s in data.get("suggestions", [])
    ]
    return JsonResponse({"suggestions": result})
