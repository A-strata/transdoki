from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from transdoki.tenancy import get_request_account

from .forms import PersonForm
from .models import Person
from .validators import validate_phone_number


class UserOwnedListView(LoginRequiredMixin, ListView):
    """Базовый View показывающий только записи текущего account (tenant)."""

    def get_queryset(self):
        return self.model.objects.filter(account=get_request_account(self.request))


class PersonCreateView(LoginRequiredMixin, CreateView):
    model = Person
    form_class = PersonForm
    template_name = "persons/person_form.html"
    success_url = reverse_lazy("persons:list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.account = get_request_account(self.request)
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
        return Person.objects.filter(account=get_request_account(self.request))

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
        return Person.objects.filter(account=get_request_account(self.request))


class PersonListView(UserOwnedListView):
    model = Person
    template_name = "persons/person_list.html"
    context_object_name = "persons"


@login_required
@require_GET
def person_search(request):
    account = get_request_account(request)
    q = request.GET.get("q", "").strip()
    qs = Person.objects.filter(account=account)
    if q:
        for part in q.split():
            qs = qs.filter(
                Q(surname__icontains=part)
                | Q(name__icontains=part)
                | Q(patronymic__icontains=part)
            )
    results = [
        {"id": p.pk, "text": str(p)}
        for p in qs.order_by("surname", "name")[:25]
    ]
    return JsonResponse({"results": results})


@login_required
@require_POST
def person_quick_create(request):
    account = get_request_account(request)
    surname = request.POST.get("surname", "").strip()
    name = request.POST.get("name", "").strip()
    patronymic = request.POST.get("patronymic", "").strip()
    phone = request.POST.get("phone", "").strip()

    errors = {}
    if not surname:
        errors["surname"] = "Обязательное поле"
    if not name:
        errors["name"] = "Обязательное поле"
    if phone:
        try:
            validate_phone_number(phone)
        except ValidationError as e:
            errors["phone"] = e.messages[0]

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    try:
        person = Person(
            surname=surname,
            name=name,
            patronymic=patronymic,
            phone=phone,
            created_by=request.user,
            account=account,
        )
        person.save()
    except IntegrityError:
        return JsonResponse(
            {"errors": {"surname": "Водитель с таким ФИО уже существует"}}, status=400
        )

    full_name = " ".join(filter(None, [surname, name, patronymic]))
    return JsonResponse({"id": person.pk, "text": full_name})
