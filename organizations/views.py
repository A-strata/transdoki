from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView
from django.core.exceptions import ValidationError

from .forms import OrganizationForm
from .models import Organization


class UserOwnedListView(LoginRequiredMixin, ListView):
    """Базовый View показывающий только записи пользователя"""
    def get_queryset(self):
        return self.model.objects.filter(created_by=self.request.user)


class OrganizationCreateView(LoginRequiredMixin, CreateView):
    model = Organization
    form_class = OrganizationForm
    template_name = 'organizations/organization_form.html'
    success_url = reverse_lazy('organizations:list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user

        try:
            return super().form_valid(form)
        except ValidationError as e:
            for field, errors in e.error_dict.items():
                for error in errors:
                    form.add_error(field, error)
            return self.form_invalid(form)
        except IntegrityError:
            form.add_error('inn', 'Организация с таким ИНН уже существует.')
            return self.form_invalid(form)


class OrganizationListView(UserOwnedListView):
    model = Organization
    template_name = 'organizations/organization_list.html'
    context_object_name = 'organizations'  # опционально, для ясности в шаблоне
