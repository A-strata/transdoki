from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView
from .models import Trip
from .forms import TripForm


class TripCreateView(CreateView):
    model = Trip
    form_class = TripForm
    template_name = 'trips/trip_form.html'
    success_url = reverse_lazy('trips:list')

class TripListView(ListView):
    model = Trip
    template_name = 'trips/trip_list.html'
    context_object_name = 'trips'  # опционально, для ясности в шаблоне