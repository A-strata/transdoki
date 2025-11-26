from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from .forms import VehicleForm
from .models import Vehicle


class UserOwnedListView(LoginRequiredMixin, ListView):
    """Базовый View показывающий только записи пользователя"""
    def get_queryset(self):
        return self.model.objects.filter(created_by=self.request.user)


class VehicleCreateView0(LoginRequiredMixin, CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'vehicles/vehicle_form.html'
    success_url = reverse_lazy('vehicles:list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        try:
            return super().form_valid(form)
        except IntegrityError:
            form.add_error('grn', 'ТС с таким номером уже существует.')
            return self.form_invalid(form)


class VehicleCreateView(LoginRequiredMixin, CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'vehicles/vehicle_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['organization_pk'] = self.kwargs['organization_pk']
        return context

    def get_success_url(self):
        return reverse(
            'organizations:detail',
            kwargs={'pk': self.kwargs['organization_pk']}
        )

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.owner_id = self.kwargs['organization_pk']
        return super().form_valid(form)


class VehicleUpdateView(LoginRequiredMixin, UpdateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'vehicles/vehicle_form.html'

    def get_queryset(self):
        return Vehicle.objects.filter(created_by=self.request.user)

    def get_success_url(self):
        return reverse(
            'organizations:detail',
            kwargs={'pk': self.object.owner.pk}
        )

    def get_context_data(self, **kwargs):  # ✅ Убрал form из параметров
        context = super().get_context_data(**kwargs)
        context['organization_pk'] = self.object.owner.pk
        return context

    def form_valid(self, form):
        try:
            return super().form_valid(form)  # ✅ Переместил в form_valid
        except IntegrityError:
            form.add_error('grn', 'ТС с таким номером уже существует.')
            return self.form_invalid(form)


class VehicleListView(UserOwnedListView):
    model = Vehicle
    template_name = 'vehicles/vehicle_list.html'
    context_object_name = 'vehicles'  # опционально, для ясности в шаблоне
