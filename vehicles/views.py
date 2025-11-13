from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView
from django.db import IntegrityError

from .forms import VehicleForm
from .models import Vehicle


class UserOwnedListView(LoginRequiredMixin, ListView):
    """Базовый View показывающий только записи пользователя"""
    def get_queryset(self):
        return self.model.objects.filter(created_by=self.request.user)


class VehicleCreateView(LoginRequiredMixin, CreateView):
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


class VehicleListView(UserOwnedListView):
    model = Vehicle
    template_name = 'vehicles/vehicle_list.html'
    context_object_name = 'vehicles'  # опционально, для ясности в шаблоне
