from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import PersonForm
from .models import Person


class UserOwnedListView(LoginRequiredMixin, ListView):
    """Базовый View показывающий только записи текущего account (tenant)."""

    def _get_request_account(self):
        account = getattr(getattr(self.request.user, "profile", None), "account", None)
        if account is None:
            raise PermissionDenied("У пользователя не найден account.")
        return account

    def get_queryset(self):
        return self.model.objects.filter(account=self._get_request_account())


class PersonCreateView(LoginRequiredMixin, CreateView):
    model = Person
    form_class = PersonForm
    template_name = "persons/person_form.html"
    success_url = reverse_lazy("persons:list")

    def _get_request_account(self):
        account = getattr(getattr(self.request.user, "profile", None), "account", None)
        if account is None:
            raise PermissionDenied("У пользователя не найден account.")
        return account

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.account = self._get_request_account()
        try:
            return super().form_valid(form)
        except IntegrityError:
            form.add_error(None, "Человек с таким ФИО уже существует.")
            return self.form_invalid(form)


class PersonUpdateView(LoginRequiredMixin, UpdateView):
    model = Person
    form_class = PersonForm
    template_name = "persons/person_form.html"
    success_url = reverse_lazy("persons:list")

    def get_queryset(self):
        account = getattr(getattr(self.request.user, "profile", None), "account", None)
        if account is None:
            raise PermissionDenied("У пользователя не найден account.")
        return Person.objects.filter(account=account)

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except IntegrityError:
            form.add_error(None, "Человек с таким ФИО уже существует.")
            return self.form_invalid(form)


class PersonDeleteView(LoginRequiredMixin, DeleteView):
    model = Person
    template_name = "persons/person_confirm_delete.html"
    success_url = reverse_lazy("persons:list")

    def get_queryset(self):
        account = getattr(getattr(self.request.user, "profile", None), "account", None)
        if account is None:
            raise PermissionDenied("У пользователя не найден account.")
        return Person.objects.filter(account=account)


class PersonListView(UserOwnedListView):
    model = Person
    template_name = "persons/person_list.html"
    context_object_name = "persons"
