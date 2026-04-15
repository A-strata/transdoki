from django import forms
from django.core.exceptions import ValidationError
from django.urls import reverse

from transdoki.enums import VatRate
from transdoki.forms import ErrorHighlightMixin

from .models import Trip, TripPoint


class TripPointForm(ErrorHighlightMixin, forms.ModelForm):
    """Форма одной точки маршрута. Используется для валидации данных из JSON."""

    class Meta:
        model = TripPoint
        fields = [
            "point_type", "organization",
            "address", "planned_date", "planned_time",
            "contact_name", "contact_phone", "loading_type",
        ]
        widgets = {
            "planned_date": forms.DateInput(attrs={"type": "date"}),
            "planned_time": forms.TimeInput(attrs={"type": "time"}),
            "contact_phone": forms.TextInput(attrs={
                "type": "tel",
                "data-phone-mask": "",
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)

        # organization не обязательна
        orig = self.fields["organization"]
        self.fields["organization"] = AjaxModelChoiceField(
            queryset=orig.queryset.none(),
            required=False,
            widget=orig.widget,
            label=orig.label,
            initial=orig.initial,
            help_text=orig.help_text,
            empty_label=orig.empty_label,
            to_field_name=orig.to_field_name,
        )

        if user and user.is_authenticated:
            self._setup_organization_validation(user)

    def _setup_organization_validation(self, user):
        from organizations.models import Organization

        account_id = getattr(getattr(user, "profile", None), "account_id", None)
        if not account_id:
            return

        full_org = Organization.objects.filter(account_id=account_id)
        field = self.fields["organization"]
        field._validation_qs = full_org

        pk = self.data.get("organization") if self.is_bound else None
        if pk:
            field.queryset = full_org.filter(pk=pk)

    def clean_organization(self):
        """
        Явная проверка, что организация принадлежит аккаунту пользователя.

        AjaxModelChoiceField._validation_qs должна фильтровать по account,
        но из-за особенностей Django ModelChoiceField валидация может
        обходиться. clean_<field> — надёжный Django-механизм, который
        вызывается ПОСЛЕ to_python и гарантированно проверяет значение.
        """
        org = self.cleaned_data.get("organization")
        if org is None:
            return None
        vqs = getattr(self.fields["organization"], "_validation_qs", None)
        if vqs is not None and not vqs.filter(pk=org.pk).exists():
            raise ValidationError("Выберите организацию из списка.")
        return org

    def clean(self):
        cleaned_data = super().clean()
        name = (cleaned_data.get("contact_name") or "").strip()
        phone = (cleaned_data.get("contact_phone") or "").strip()
        cleaned_data["contact_name"] = name
        cleaned_data["contact_phone"] = phone
        if bool(name) ^ bool(phone):
            msg = "Заполните и имя, и телефон контакта (или оставьте оба поля пустыми)."
            self.add_error("contact_name", msg)
            self.add_error("contact_phone", msg)
        return cleaned_data


class AjaxModelChoiceField(forms.ModelChoiceField):
    """
    ModelChoiceField с двумя queryset-ами:
    - self.queryset        — минимальный (только текущее значение), для рендера <option>
    - self._validation_qs  — полный по account, для валидации submitted pk

    Это позволяет не грузить все записи в HTML, сохраняя серверную валидацию.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("empty_label", "")
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if value in self.empty_values:
            return None
        qs = getattr(self, "_validation_qs", self.queryset)
        try:
            return qs.get(pk=value)
        except (ValueError, TypeError, qs.model.DoesNotExist):
            raise ValidationError(
                self.error_messages["invalid_choice"],
                code="invalid_choice",
                params={"value": value},
            )
from .validators import (
    validate_client_cannot_be_carrier,
    validate_costs_by_our_company_role,
    validate_forwarder,
    validate_our_company_participation,
    validate_trailer_for_truck,
    validate_unique_trip_number_and_date,
    validate_vehicles_belong_to_carrier,
)


class TripForm(ErrorHighlightMixin, forms.ModelForm):
    num_of_trip = forms.IntegerField(
        label="Номер заявки", required=False, disabled=True
    )

    class Meta:
        model = Trip
        exclude = [
            "created_by", "created_at", "updated_at", "account",
            "loading_address", "unloading_address",
            "planned_loading_date", "planned_unloading_date",
            "actual_loading_date", "actual_unloading_date",
            "loading_contact_name", "loading_contact_phone",
            "unloading_contact_name", "unloading_contact_phone",
            "loading_type", "unloading_type",
            # управляются через action фиксации, не через форму редактирования
            "client_financial_status", "client_total_fixed",
            "carrier_financial_status", "carrier_total_fixed",
        ]
        labels = {
            "cargo": "Наименование груза",
            "weight": "Вес",
            "volume": "Объём",
            "comments": "Комментарии",
        }
        widgets = {
            "date_of_trip": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    # FK-поля, переводимые в AjaxModelChoiceField
    _AJAX_FIELDS = ["client", "carrier", "driver", "truck", "trailer"]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.current_org = kwargs.pop("current_org", None)
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)

        # Показываем номер рейса только при редактировании
        if self.instance and self.instance.pk:
            self.fields["num_of_trip"].initial = self.instance.num_of_trip
        else:
            self.fields.pop("num_of_trip", None)

        # Заменяем FK-поля на AjaxModelChoiceField (пустой queryset для рендера)
        for fname in self._AJAX_FIELDS:
            if fname not in self.fields:
                continue
            orig = self.fields[fname]
            self.fields[fname] = AjaxModelChoiceField(
                queryset=orig.queryset.none(),
                required=orig.required,
                widget=orig.widget,
                label=orig.label,
                initial=orig.initial,
                help_text=orig.help_text,
                empty_label=orig.empty_label,
                to_field_name=orig.to_field_name,
            )

        for vat_field in ("client_vat_rate", "carrier_vat_rate"):
            if vat_field in self.fields:
                self.fields[vat_field].empty_value = None
                self.fields[vat_field].widget.choices = [
                    ("", "Без НДС"),
                ] + [(c.value, c.label) for c in VatRate]

        if self.user and self.user.is_authenticated:
            self._apply_queryset_filters()

        if self.instance and self.instance.pk:
            self._lock_fixed_finance_fields()

    def _apply_queryset_filters(self):
        from organizations.models import Organization
        from persons.models import Person
        from vehicles.models import Vehicle

        account_id = getattr(getattr(self.user, "profile", None), "account_id", None)
        if not account_id:
            return  # queryset уже none() из __init__

        full_org = Organization.objects.filter(account_id=account_id)
        full_person = Person.objects.filter(account_id=account_id)
        full_truck = Vehicle.objects.filter(account_id=account_id, vehicle_type__in=["truck", "single"])
        full_trailer = Vehicle.objects.filter(account_id=account_id, vehicle_type="trailer")

        org_search_url = reverse("organizations:search")
        person_search_url = reverse("persons:search")
        vehicle_search_url = reverse("vehicles:search")

        for fname in ["client", "carrier"]:
            self._setup_ajax_field(fname, full_org, org_search_url)

        self._setup_ajax_field("driver", full_person, person_search_url)
        self._setup_ajax_field("truck", full_truck, vehicle_search_url, search_type="truck")
        self._setup_ajax_field("trailer", full_trailer, vehicle_search_url, search_type="trailer")

        # Экспедитор: только own-фирмы аккаунта. Для редактирования —
        # существующее значение; для создания — только current_org
        # (по требованию UX: единственный допустимый выбор).
        # Поле скрытое — управляется через карточки ролей в trip_form_role.js.
        if "forwarder" in self.fields:
            forwarder_field = self.fields["forwarder"]
            forwarder_field.required = False
            forwarder_field.widget = forms.HiddenInput()
            own_orgs = Organization.objects.own_for(account_id)
            forwarder_field._validation_qs = own_orgs

            current = getattr(self.instance, "forwarder", None)
            current_pk = current.pk if (current and current.pk) else None
            if current_pk:
                forwarder_field.queryset = own_orgs.filter(pk=current_pk)
            elif self.current_org is not None:
                forwarder_field.queryset = own_orgs.filter(pk=self.current_org.pk)
            else:
                forwarder_field.queryset = own_orgs.none()

    def _lock_fixed_finance_fields(self):
        from .models import CostUnit, FinancialStatus

        def lock(fields):
            for f in fields:
                if f in self.fields:
                    self.fields[f].disabled = True

        inst = self.instance
        if inst.client_financial_status != FinancialStatus.OPEN:
            lock([
                "client_cost", "client_cost_unit", "client_payment_method",
                "client_vat_rate", "payment_condition", "payment_term", "client_quantity",
            ])
            if inst.client_cost_unit == CostUnit.RUB_PER_KG:
                lock(["weight"])
            elif inst.client_cost_unit == CostUnit.RUB_PER_CBM:
                lock(["volume"])

        if inst.carrier_financial_status != FinancialStatus.OPEN:
            lock([
                "carrier_cost", "carrier_cost_unit", "carrier_payment_method",
                "carrier_vat_rate", "carrier_payment_condition", "carrier_payment_term",
                "carrier_quantity",
            ])
            if inst.carrier_cost_unit == CostUnit.RUB_PER_KG:
                lock(["weight"])
            elif inst.carrier_cost_unit == CostUnit.RUB_PER_CBM:
                lock(["volume"])

    def _setup_ajax_field(self, fname, full_qs, search_url, search_type=""):
        """Устанавливает validation queryset, display queryset (текущее значение)
        и data-атрибуты для AJAX-автокомплита."""
        field = self.fields[fname]
        field._validation_qs = full_qs

        # display queryset: текущее значение (edit), initial (copy) или POST-данные (ошибка валидации)
        current = getattr(self.instance, fname, None)
        current_pk = current.pk if (current and current.pk) else None
        initial_pk = self.initial.get(fname) if not current_pk else None
        submitted_pk = self.data.get(fname) if (self.is_bound and not current_pk and not initial_pk) else None
        pk = current_pk or initial_pk or submitted_pk
        if pk:
            field.queryset = full_qs.filter(pk=pk)
        # else: остаётся none()

        field.widget.attrs["data-search-url"] = search_url
        if search_type:
            field.widget.attrs["data-search-type"] = search_type

    def clean(self):
        cleaned_data = super().clean()

        if self.user:
            validate_unique_trip_number_and_date(
                user=self.user,
                num_of_trip=cleaned_data.get("num_of_trip"),
                date_of_trip=cleaned_data.get("date_of_trip"),
                instance=self.instance,
            )
            validate_client_cannot_be_carrier(
                client=cleaned_data.get("client"), carrier=cleaned_data.get("carrier")
            )
            validate_forwarder(
                forwarder=cleaned_data.get("forwarder"),
                client=cleaned_data.get("client"),
                carrier=cleaned_data.get("carrier"),
                current_org=self.current_org,
            )
            validate_our_company_participation(
                client=cleaned_data.get("client"),
                carrier=cleaned_data.get("carrier"),
                forwarder=cleaned_data.get("forwarder"),
            )
            validate_trailer_for_truck(
                truck=cleaned_data.get("truck"), trailer=cleaned_data.get("trailer")
            )
            validate_vehicles_belong_to_carrier(
                truck=cleaned_data.get("truck"),
                trailer=cleaned_data.get("trailer"),
                carrier=cleaned_data.get("carrier"),
            )
            validate_costs_by_our_company_role(
                client=cleaned_data.get("client"),
                carrier=cleaned_data.get("carrier"),
                client_cost=cleaned_data.get("client_cost"),
                carrier_cost=cleaned_data.get("carrier_cost"),
                forwarder=cleaned_data.get("forwarder"),
            )

        return cleaned_data


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single_file_clean = super().clean

        if isinstance(data, (list, tuple)):
            return [single_file_clean(item, initial) for item in data]

        return [single_file_clean(data, initial)]


class TripAttachmentUploadForm(ErrorHighlightMixin, forms.Form):
    files = MultipleFileField(
        label="Файлы",
        required=True,
        widget=MultipleFileInput(attrs={"multiple": True}),
    )
