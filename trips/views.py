from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView
from .models import Trip
from .forms import TripForm
from .services import TNGenerator
from django.shortcuts import get_object_or_404


class TripCreateView(CreateView):
    model = Trip
    form_class = TripForm
    template_name = 'trips/trip_form.html'
    success_url = reverse_lazy('trips:list')

class TripListView(ListView):
    model = Trip
    template_name = 'trips/trip_list.html'
    context_object_name = 'trips'  # опционально, для ясности в шаблоне

def print_tn(request, pk):
    """View для генерации ТН"""
    trip = get_object_or_404(Trip, id=pk)
    file_path = TNGenerator.generate_tn(trip)
    return TNGenerator.create_file_response(file_path, trip)