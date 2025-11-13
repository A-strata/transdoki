from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from .forms import TripForm
from .models import Trip
from .services import TNGenerator


class UserOwnedListView(LoginRequiredMixin, ListView):
    """Базовый View показывающий только записи пользователя"""
    def get_queryset(self):
        return self.model.objects.filter(created_by=self.request.user)


class TripCreateView(LoginRequiredMixin, CreateView):
    model = Trip
    form_class = TripForm
    template_name = 'trips/trip_form.html'
    success_url = reverse_lazy('trips:list')


class TripListView(UserOwnedListView):
    model = Trip
    template_name = 'trips/trip_list.html'
    context_object_name = 'trips'  # опционально, для ясности в шаблоне


def print_tn(_request, pk):
    """View для генерации ТН"""
    trip = get_object_or_404(Trip, id=pk)
    file_path = TNGenerator.generate_tn(trip)
    return TNGenerator.create_file_response(file_path, trip)
