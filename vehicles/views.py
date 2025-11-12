from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView
from .models import Vehicle
from .forms import VehicleForm
from django.contrib.auth.mixins import LoginRequiredMixin


class VehicleCreateView(LoginRequiredMixin, CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'vehicles/vehicle_form.html'
    success_url = reverse_lazy('vehicles:list')

class VehicleListView(LoginRequiredMixin, ListView):
    model = Vehicle
    template_name = 'vehicles/vehicle_list.html'
    context_object_name = 'vehicles'  # опционально, для ясности в шаблоне