from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView
from django.db import IntegrityError
from django.core.exceptions import PermissionDenied

from .forms import TripForm
from .models import Trip
from .services import TNGenerator
from organizations.views import Organization
from persons.views import Person
from vehicles.views import Vehicle


class UserOwnedListView(LoginRequiredMixin, ListView):
    """Базовый View показывающий только записи пользователя"""
    def get_queryset(self):
        return self.model.objects.filter(created_by=self.request.user)


class TripCreateView(LoginRequiredMixin, CreateView):
    model = Trip
    form_class = TripForm
    template_name = 'trips/trip_form.html'
    success_url = reverse_lazy('trips:list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        try:
            return super().form_valid(form)
        except IntegrityError:
            form.add_error(
                None,
                'Заявка с таким номером и датой уже существует.'
            )
            return self.form_invalid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Фильтруем queryset для всех ForeignKey полей
        form.fields['client'].queryset = Organization.objects.filter(
            created_by=self.request.user)
        form.fields['consignor'].queryset = Organization.objects.filter(
            created_by=self.request.user)
        form.fields['consignee'].queryset = Organization.objects.filter(
            created_by=self.request.user)
        form.fields['carrier'].queryset = Organization.objects.filter(
            created_by=self.request.user)
        form.fields['driver'].queryset = Person.objects.filter(
            created_by=self.request.user)
        form.fields['truck'].queryset = Vehicle.objects.filter(
            created_by=self.request.user, vehicle_type__in=['truck', 'single'])
        form.fields['trailer'].queryset = Vehicle.objects.filter(
            created_by=self.request.user, vehicle_type='trailer')
        return form


class TripListView(UserOwnedListView):
    model = Trip
    template_name = 'trips/trip_list.html'
    context_object_name = 'trips'  # опционально, для ясности в шаблоне


def print_tn(request, pk):
    """View для генерации ТН"""
    trip = get_object_or_404(Trip, id=pk)
    file_path = TNGenerator.generate_tn(trip)

    if trip.created_by != request.user:
        raise PermissionDenied(
            "У вас нет доступа к этой транспортной накладной"
        )

    file_path = TNGenerator.generate_tn(trip)
    return TNGenerator.create_file_response(file_path, trip)
