from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from django.core.exceptions import PermissionDenied
import logging

from .forms import TripForm
from .models import Trip
from .services import TNGenerator


logger = logging.getLogger('security')


class UserOwnedListView(LoginRequiredMixin, ListView):
    """Базовый View показывающий только записи пользователя"""
    def get_queryset(self):
        return self.model.objects.filter(created_by=self.request.user)


class TripCreateView(LoginRequiredMixin, CreateView):
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
