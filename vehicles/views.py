from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView
from .models import Vehicle
from .forms import VehicleForm


class VehicleCreateView(CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'vehicles/vehicle_form.html'
    success_url = reverse_lazy('vehicles:list')

class VehicleListView(ListView):
    model = Vehicle
    template_name = 'vehicles/vehicle_list.html'
    context_object_name = 'vehicles'  # опционально, для ясности в шаблоне