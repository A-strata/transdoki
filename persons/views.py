from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

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

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        try:
            return super().form_valid(form)
        except IntegrityError:
            form.add_error(None, 'Человек с таким ФИО уже существует.')
            return self.form_invalid(form)


class PersonUpdateView(LoginRequiredMixin, UpdateView):
    model = Person
    form_class = PersonForm
    template_name = 'persons/person_form.html'
    success_url = reverse_lazy('persons:list')

    def get_queryset(self):
        # Пользователь может редактировать только своих людей
        return Person.objects.filter(created_by=self.request.user)

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except IntegrityError:
            form.add_error(None, 'Человек с таким ФИО уже существует.')
            return self.form_invalid(form)


class PersonDeleteView(LoginRequiredMixin, DeleteView):
    model = Person
    template_name = 'persons/person_confirm_delete.html'
    success_url = reverse_lazy('persons:list')

    def get_queryset(self):
        # Пользователь может удалять только своих людей
        return Person.objects.filter(created_by=self.request.user)


class PersonListView(UserOwnedListView):
    model = Person
    template_name = 'persons/person_list.html'
    context_object_name = 'persons'  # опционально, для ясности в шаблоне
