from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView
from .models import Person
from .forms import PersonForm


class PersonCreateView(CreateView):
    model = Person
    form_class = PersonForm
    template_name = 'persons/person_form.html'
    success_url = reverse_lazy('persons:list')

class PersonListView(ListView):
    model = Person
    template_name = 'persons/person_list.html'
    context_object_name = 'persons'  # опционально, для ясности в шаблоне