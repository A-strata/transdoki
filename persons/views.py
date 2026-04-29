from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from organizations.models import Organization
from transdoki.search import AjaxSearchView, CarrierGroupingMixin
from transdoki.tenancy import get_request_account

from .forms import PersonForm, PersonQuickForm
from .models import Person


class PersonCreateView(LoginRequiredMixin, CreateView):
    model = Person
    form_class = PersonForm
    template_name = "persons/person_form.html"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.account = get_request_account(self.request)
        form.instance.employer = getattr(self.request, "current_org", None)
        try:
            return super().form_valid(form)
        except IntegrityError:
            form.add_error(None, "Человек с таким ФИО уже существует.")
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_org"] = getattr(self.request, "current_org", None)
        return context

    def get_success_url(self):
        return reverse("persons:detail", kwargs={"pk": self.object.pk})


class PersonUpdateView(LoginRequiredMixin, UpdateView):
    model = Person
    form_class = PersonForm
    template_name = "persons/person_form.html"

    def get_queryset(self):
        return Person.objects.for_account(get_request_account(self.request))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_org"] = self.object.employer
        next_url = self.request.GET.get("next", "")
        if next_url:
            context["next_url"] = next_url
        return context

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        try:
            return super().form_valid(form)
        except IntegrityError:
            form.add_error(None, "Человек с таким ФИО уже существует.")
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse("persons:detail", kwargs={"pk": self.object.pk})


class PersonDeleteView(LoginRequiredMixin, DeleteView):
    model = Person
    template_name = "persons/person_confirm_delete.html"

    def get_queryset(self):
        return Person.objects.for_account(get_request_account(self.request))

    def get_success_url(self):
        return reverse("persons:list")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        try:
            self.object.delete()
            if is_ajax:
                return JsonResponse({"ok": True})
            messages.success(request, f"«{self.object}» удалён.")
            return redirect(self.get_success_url())
        except ProtectedError:
            if is_ajax:
                return JsonResponse(
                    {"ok": False, "error": "Невозможно удалить: есть связанные рейсы или путевые листы."},
                    status=409,
                )
            messages.error(
                request,
                "Невозможно удалить: есть связанные рейсы или путевые листы.",
            )
            return redirect(self.get_success_url())


class PersonDetailView(LoginRequiredMixin, DetailView):
    model = Person
    template_name = "persons/person_detail.html"

    def get_queryset(self):
        return Person.objects.for_account(get_request_account(self.request))


class PersonListView(LoginRequiredMixin, ListView):
    model = Person
    template_name = "persons/person_list.html"
    context_object_name = "persons"

    def get_queryset(self):
        current_org = self.request.current_org
        if current_org is None:
            return Person.objects.none()
        return Person.objects.filter(
            employer=current_org,
        ).select_related("employer")


class PersonSearchView(CarrierGroupingMixin, AjaxSearchView):
    """AJAX-поиск водителей для autocomplete-полей.

    GET-параметры:
      q          — поиск по surname / name / patronymic (AND между словами,
                   OR между полями).
      carrier_id — pk перевозчика (свой/внешний — без разницы); STRICT-фильтр
                   по employer_id = carrier_id. Если carrier_id невалиден /
                   не из аккаунта — плоский ответ.

    Strict-режим — полная симметрия с VehicleSearchView: после выбора
    перевозчика дропдаун водителя показывает либо его водителей, либо
    empty-state с кнопкой «+ Добавить водителя» (quick-create подставит
    employer = carrier). Серверный валидатор «driver.employer == carrier»
    в trips/forms.py НЕ добавлен — клиентский UX направляет, бэк не
    запрещает; при необходимости валидатор легко добавить отдельно.
    """

    model = Person
    search_fields = ("surname", "name", "patronymic")
    order_by = ("surname", "name")
    owner_field = "employer"
    strict_carrier = True
    empty_carrier_hint_text = (
        "У перевозчика «{carrier}» пока нет ни одного водителя"
    )


@login_required
@require_POST
def person_quick_create(request):
    """Быстрое создание водителя из модалок (form рейса и карточка организации).

    Валидацию и нормализацию (в т.ч. телефона) отдаём в PersonQuickForm —
    единая точка истины с PersonForm.

    Контракт с клиентом:
      * входной параметр employer приходит под именем `employer_id`
        (исторически; оба шаблона шлют именно так) → перекладываем в `employer`
        перед биндингом формы;
      * ошибки мапятся обратно на `employer_id`, чтобы data-err="employer_id"
        в шаблоне отрисовал сообщение у правильного поля.
    """
    account = get_request_account(request)

    post = request.POST.copy()
    if not post.get("employer"):
        post["employer"] = post.get("employer_id", "")

    form = PersonQuickForm(post)
    # Tenant-изоляция: запрет выбрать чужую организацию как работодателя.
    form.fields["employer"].queryset = Organization.objects.for_account(account)
    form.fields["employer"].required = True
    form.fields["employer"].error_messages = {
        "required": "Обязательное поле",
        "invalid_choice": "Организация не найдена",
    }
    form.fields["surname"].error_messages = {"required": "Обязательное поле"}
    form.fields["name"].error_messages = {"required": "Обязательное поле"}

    if not form.is_valid():
        errors = {}
        for field, errs in form.errors.items():
            key = "employer_id" if field == "employer" else field
            errors[key] = errs[0]
        return JsonResponse({"errors": errors}, status=400)

    try:
        person = form.save(commit=False)
        person.account = account
        person.created_by = request.user
        person.save()
    except IntegrityError:
        return JsonResponse(
            {"errors": {"surname": "Водитель с таким ФИО уже существует"}},
            status=400,
        )

    return JsonResponse({"id": person.pk, "text": str(person)})
