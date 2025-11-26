from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

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
            # Обрабатываем ошибки валидации из модели
            for field, errors in e.error_dict.items():
                for error in errors:
                    form.add_error(field, error)
            return self.form_invalid(form)
        except IntegrityError:
            # Обрабатываем ошибку уникальности ИНН
            form.add_error('inn', 'Организация с таким ИНН уже существует.')
            return self.form_invalid(form)

    def get_success_url(self):
        """После создания перенаправляем на детальную страницу организации"""
        return reverse('organizations:detail', kwargs={'pk': self.object.pk})


class OrganizationUpdateView(LoginRequiredMixin, UpdateView):
    model = Organization
    form_class = OrganizationForm
    template_name = 'organizations/organization_form.html'

    def get_queryset(self):
        return Organization.objects.filter(created_by=self.request.user)

    def form_valid(self, form):
        # Просто сохраняем организацию, без машин
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('organizations:detail', kwargs={'pk': self.object.pk})


class OrganizationListView(UserOwnedListView):
    model = Organization
    template_name = 'organizations/organization_list.html'
    context_object_name = 'organizations'  # опционально, для ясности в шаблоне


class OrganizationDetailView(LoginRequiredMixin, DetailView):
    model = Organization
    template_name = 'organizations/organization_detail.html'

    def get_queryset(self):
        return Organization.objects.filter(created_by=self.request.user)
