from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from .forms import PersonForm
from .models import Person


class UserOwnedListView(LoginRequiredMixin, ListView):
    """Базовый View показывающий только записи пользователя"""
    def get_queryset(self):
        return self.model.objects.filter(created_by=self.request.user)


class PersonCreateView(LoginRequiredMixin, CreateView):
    model = Person
    form_class = PersonForm
    template_name = 'persons/person_form.html'
    success_url = reverse_lazy('persons:list')


class PersonListView(UserOwnedListView):
    model = Person
    template_name = 'persons/person_list.html'
    context_object_name = 'persons'  # опционально, для ясности в шаблоне
