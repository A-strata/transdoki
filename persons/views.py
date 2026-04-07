from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError, Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from transdoki.tenancy import get_request_account
from transdoki.views import UserOwnedListView

from organizations.models import Organization

from .forms import PersonForm
from .models import Person
from .validators import validate_phone_number


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
        try:
            self.object.delete()
            messages.success(request, f"«{self.object}» удалён.")
            return redirect(self.get_success_url())
        except ProtectedError:
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


@login_required
@require_GET
def person_search(request):
    account = get_request_account(request)
    q = request.GET.get("q", "").strip()
    carrier_id = request.GET.get("carrier_id", "").strip()

    base_qs = Person.objects.for_account(account)

    def apply_q(qs):
        filtered = qs
        for part in q.split():
            filtered = filtered.filter(
                Q(surname__icontains=part)
                | Q(name__icontains=part)
                | Q(patronymic__icontains=part)
            )
        return filtered

    def serialize(qs):
        return [
            {"id": p.pk, "text": str(p)}
            for p in qs.order_by("surname", "name")[:25]
        ]

    if not carrier_id.isdigit():
        return JsonResponse({
            "carrier": [],
            "others": serialize(apply_q(base_qs) if q else base_qs),
            "hint": None,
        })

    org = (
        Organization.objects.for_account(account)
        .filter(pk=int(carrier_id))
        .first()
    )

    if not org or not org.is_own_company:
        others_qs = apply_q(base_qs) if q else base_qs
        return JsonResponse({
            "carrier": [],
            "others": serialize(others_qs),
            "hint": "no_employer_data",
        })

    carrier_qs = base_qs.filter(employer_id=org.pk)
    carrier_results = serialize(apply_q(carrier_qs) if q else carrier_qs)

    if not carrier_results and not q:
        others_qs = base_qs
        return JsonResponse({
            "carrier": [],
            "others": serialize(others_qs),
            "hint": "no_employer_data",
        })

    others_qs = apply_q(base_qs.exclude(employer_id=org.pk)) if q else None
    return JsonResponse({
        "carrier": carrier_results,
        "others": serialize(others_qs) if others_qs is not None else [],
        "hint": None,
    })


@login_required
@require_POST
def person_quick_create(request):
    account = get_request_account(request)
    surname = request.POST.get("surname", "").strip()
    name = request.POST.get("name", "").strip()
    patronymic = request.POST.get("patronymic", "").strip()
    phone = request.POST.get("phone", "").strip()

    employer_id = request.POST.get("employer_id", "").strip()

    errors = {}
    if not surname:
        errors["surname"] = "Обязательное поле"
    if not name:
        errors["name"] = "Обязательное поле"
    if not employer_id:
        errors["employer_id"] = "Обязательное поле"
    elif not employer_id.isdigit():
        errors["employer_id"] = "Некорректное значение"
    if phone:
        try:
            validate_phone_number(phone)
        except ValidationError as e:
            errors["phone"] = e.messages[0]

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    employer = Organization.objects.for_account(account).filter(pk=int(employer_id)).first()
    if not employer:
        return JsonResponse(
            {"errors": {"employer_id": "Организация не найдена"}}, status=400
        )

    try:
        person = Person(
            surname=surname,
            name=name,
            patronymic=patronymic,
            phone=phone,
            created_by=request.user,
            account=account,
            employer=employer,
        )
        person.save()
    except IntegrityError:
        return JsonResponse(
            {"errors": {"surname": "Водитель с таким ФИО уже существует"}}, status=400
        )

    full_name = " ".join(filter(None, [surname, name, patronymic]))
    return JsonResponse({"id": person.pk, "text": full_name})
