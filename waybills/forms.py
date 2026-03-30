from itertools import chain

from django import forms
from django.urls import reverse
from django.utils import timezone

from transdoki.forms import ErrorHighlightMixin

from organizations.models import Organization
from persons.models import Person
from trips.models import Trip
from vehicles.models import Vehicle

from .models import Waybill, WaybillEvent, RoutePoint


class AjaxModelChoiceField(forms.ModelChoiceField):
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
            raise forms.ValidationError(
                self.error_messages["invalid_choice"],
                code="invalid_choice",
                params={"value": value},
            )


def _is_event(record):
    return isinstance(record, WaybillEvent)


def _is_route_point(record):
    return isinstance(record, RoutePoint)


def _record_code(record):
    if _is_event(record):
        return record.event_type
    if _is_route_point(record):
        return record.point_type
    return None


def _record_kind(record):
    if _is_event(record):
        return "event"
    if _is_route_point(record):
        return "route_point"
    return None


def _timeline_sort_key(record):
    return (
        record.timestamp,
        0 if _is_event(record) else 1,
        record.pk or 0,
    )


def get_waybill_timeline(waybill, current_instance=None):
    """
    Возвращает общую ленту записей путевого листа:
    WaybillEvent + RoutePoint, отсортированную по времени.

    Если current_instance передан, он исключается из результата
    (важно при редактировании).
    """
    events = waybill.events.all()
    route_points = waybill.route_points.all()

    records = []

    for item in chain(events, route_points):
        if current_instance is not None:
            if isinstance(item, current_instance.__class__) and item.pk == current_instance.pk:
                continue
        if item.timestamp:
            records.append(item)

    records.sort(key=_timeline_sort_key)
    return records


def get_previous_waybill_record(waybill, timestamp, current_instance=None):
    """
    Возвращает предыдущую запись по общей хронологии путевого листа
    среди WaybillEvent и RoutePoint.

    Если редактируется существующая запись, она исключается из сравнения.
    """
    timeline = get_waybill_timeline(waybill, current_instance=current_instance)
    previous = None

    for item in timeline:
        if item.timestamp < timestamp:
            previous = item
        else:
            break

    return previous


def get_next_waybill_record(waybill, timestamp, current_instance=None):
    """
    Возвращает следующую запись по общей хронологии путевого листа
    среди WaybillEvent и RoutePoint.

    Если редактируется существующая запись, она исключается из сравнения.
    """
    timeline = get_waybill_timeline(waybill, current_instance=current_instance)

    for item in timeline:
        if item.timestamp > timestamp:
            return item

    return None


def waybill_has_event_type(waybill, event_type, current_instance=None):
    qs = waybill.events.filter(event_type=event_type)

    if current_instance is not None and isinstance(current_instance, WaybillEvent) and current_instance.pk:
        qs = qs.exclude(pk=current_instance.pk)

    return qs.exists()


def validate_transition(previous_record, current_code, current_kind):
    """
    Валидирует переход previous_record -> current_code
    по общей ленте хронологии.
    Возвращает текст ошибки или None.
    """
    prev_code = _record_code(previous_record) if previous_record else None
    prev_kind = _record_kind(previous_record) if previous_record else None

    if previous_record is None:
        if current_kind == "event":
            if current_code not in ("OUT", "TAKE"):
                return "Первой записью в путевом листе может быть только OUT или TAKE."
        else:
            return "Маршрутная точка не может быть первой записью. Сначала должен быть OUT или TAKE."
        return None

    if prev_code == "RETURN":
        return "После RETURN нельзя добавлять записи."

    if prev_code == "GIVE":
        if current_code != "TAKE":
            return "После GIVE должен быть TAKE, прежде чем работа может продолжиться."

    if prev_code == "OUT" and current_code == "TAKE":
        return "После OUT нельзя сразу делать TAKE."

    if prev_code == "TAKE" and current_code == "TAKE":
        return "После TAKE нельзя сразу делать TAKE."

    if prev_code == "GIVE" and current_code == "GIVE":
        return "После GIVE нельзя сразу делать GIVE."

    if prev_code == "GIVE" and current_code == "RETURN":
        return "После GIVE нельзя сразу делать RETURN."

    if prev_code == "LOAD" and current_code == "LOAD":
        return "Нельзя делать LOAD сразу после LOAD."

    if prev_code == "UNLOAD" and current_code == "UNLOAD":
        return "Нельзя делать UNLOAD сразу после UNLOAD."

    if prev_code in ("OUT", "TAKE") and current_kind == "route_point" and current_code != "LOAD":
        return f"После {prev_code} первой маршрутной точкой должен быть LOAD."

    if current_code == "RETURN" and prev_code != "UNLOAD":
        return "RETURN допустим только после UNLOAD."

    if current_code == "UNLOAD" and prev_code in ("OUT", "TAKE"):
        return f"После {prev_code} нельзя сразу делать UNLOAD. Сначала должен быть LOAD."

    if prev_kind == "event" and prev_code == "GIVE" and current_kind == "route_point":
        return "Нельзя добавлять маршрутную точку сразу после GIVE."

    return None


def validate_next_transition(current_code, current_kind, next_record):
    """
    Валидирует переход current_code -> next_record
    для случаев вставки/редактирования между существующими записями.
    Возвращает текст ошибки или None.
    """
    if next_record is None:
        return None

    next_code = _record_code(next_record)
    next_kind = _record_kind(next_record)

    if current_code == "RETURN":
        return "RETURN должен быть последней записью."

    if current_code == "GIVE" and next_code != "TAKE":
        return "После GIVE должен идти TAKE."

    if current_code == "OUT" and next_code == "TAKE":
        return "После OUT нельзя сразу делать TAKE."

    if current_code == "TAKE" and next_code == "TAKE":
        return "После TAKE нельзя сразу делать TAKE."

    if current_code == "GIVE" and next_code == "GIVE":
        return "После GIVE нельзя сразу делать GIVE."

    if current_code == "GIVE" and next_code == "RETURN":
        return "После GIVE нельзя сразу делать RETURN."

    if current_code == "GIVE" and next_kind == "route_point":
        return "Нельзя добавлять маршрутную точку сразу после GIVE."

    if current_code == "LOAD" and next_code == "LOAD":
        return "Нельзя делать LOAD сразу после LOAD."

    if current_code == "UNLOAD" and next_code == "UNLOAD":
        return "Нельзя делать UNLOAD сразу после UNLOAD."

    if current_code in ("OUT", "TAKE") and next_kind == "route_point" and next_code != "LOAD":
        return f"После {current_code} первой маршрутной точкой должен быть LOAD."

    if current_code in ("OUT", "TAKE") and next_code == "UNLOAD":
        return f"После {current_code} нельзя сразу делать UNLOAD. Сначала должен быть LOAD."

    if next_code == "RETURN" and current_code != "UNLOAD":
        return "Если после этой записи идет RETURN, перед ним должен быть UNLOAD."

    return None


class BaseStyledModelForm(ErrorHighlightMixin, forms.ModelForm):
    """Базовое добавление css-классов ко всем полям."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css_class} tms-input".strip()


class WaybillForm(BaseStyledModelForm):
    organization = AjaxModelChoiceField(
        queryset=Organization.objects.none(),
        label="Организация",
        required=True,
    )
    driver = AjaxModelChoiceField(
        queryset=Person.objects.none(),
        label="Водитель",
        required=True,
    )
    truck = AjaxModelChoiceField(
        queryset=Vehicle.objects.none(),
        label="Автомобиль",
        required=True,
    )
    trailer = AjaxModelChoiceField(
        queryset=Vehicle.objects.none(),
        label="Прицеп",
        required=False,
    )

    class Meta:
        model = Waybill
        fields = ["date", "organization", "driver", "truck", "trailer"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, account=None, **kwargs):
        super().__init__(*args, **kwargs)
        if account:
            self._setup_ajax_fields(account)

    def _setup_ajax_field(self, fname, full_qs, search_url, search_type="", open_on_focus=False):
        field = self.fields[fname]
        field._validation_qs = full_qs
        current = getattr(self.instance, fname, None)
        initial_pk = self.initial.get(fname) if not (current and current.pk) else None
        if current and current.pk:
            field.queryset = full_qs.filter(pk=current.pk)
        elif initial_pk:
            field.queryset = full_qs.filter(pk=initial_pk)
        field.widget.attrs["data-search-url"] = search_url
        if search_type:
            field.widget.attrs["data-search-type"] = search_type
        if open_on_focus:
            field.widget.attrs["data-open-on-focus"] = "1"

    def _setup_ajax_fields(self, account):
        self._setup_ajax_field(
            "organization",
            Organization.objects.filter(account=account, is_own_company=True),
            reverse("organizations:search") + "?own=1",
            open_on_focus=True,
        )
        self._setup_ajax_field(
            "driver",
            Person.objects.filter(account=account),
            reverse("persons:search"),
        )
        self._setup_ajax_field(
            "truck",
            Vehicle.objects.filter(account=account, owner__is_own_company=True),
            reverse("vehicles:search") + "?own=1",
            "truck",
        )
        self._setup_ajax_field(
            "trailer",
            Vehicle.objects.filter(account=account, owner__is_own_company=True),
            reverse("vehicles:search") + "?own=1",
            "trailer",
        )

    def clean(self):
        cleaned_data = super().clean()
        truck = cleaned_data.get("truck")
        trailer = cleaned_data.get("trailer")
        if truck and trailer and truck == trailer:
            self.add_error("trailer", "Прицеп не может совпадать с грузовиком.")
        return cleaned_data


class WaybillEventForm(BaseStyledModelForm):
    class Meta:
        model = WaybillEvent
        fields = [
            "event_type",
            "timestamp",
            "odometer",
        ]
        widgets = {
            "event_type": forms.Select(),
            "timestamp": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                },
                format="%Y-%m-%dT%H:%M",
            ),
            "odometer": forms.NumberInput(
                attrs={
                    "min": 0,
                    "step": 1,
                    "placeholder": "Показание одометра",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.waybill = kwargs.pop("waybill", None)
        super().__init__(*args, **kwargs)

        if not self.instance.pk and "timestamp" in self.fields:
            self.fields["timestamp"].initial = timezone.localtime().strftime("%Y-%m-%dT%H:%M")

    def clean_odometer(self):
        value = self.cleaned_data["odometer"]
        if value is None:
            raise forms.ValidationError("Показание одометра обязательно.")
        if value < 0:
            raise forms.ValidationError("Показание одометра не может быть отрицательным.")
        return value

    def clean(self):
        cleaned_data = super().clean()

        if self.waybill and getattr(self.waybill, "status", None) == Waybill.Status.CLOSED:
            raise forms.ValidationError("Путевой лист закрыт. Добавление событий запрещено.")

        event_type = cleaned_data.get("event_type")
        timestamp = cleaned_data.get("timestamp")
        odometer = cleaned_data.get("odometer")

        if event_type and event_type not in ("OUT", "TAKE", "GIVE", "RETURN"):
            self.add_error("event_type", "Допустимы только: OUT, TAKE, GIVE, RETURN.")

        if not timestamp:
            self.add_error("timestamp", "Дата и время обязательны.")

        if not self.waybill or not event_type or not timestamp or odometer is None:
            return cleaned_data

        current_instance = self.instance if self.instance.pk else None

        if event_type == "OUT" and waybill_has_event_type(self.waybill, "OUT", current_instance=current_instance):
            self.add_error("event_type", "В одном путевом листе может быть только один OUT.")

        if event_type == "RETURN" and waybill_has_event_type(self.waybill, "RETURN", current_instance=current_instance):
            self.add_error("event_type", "В одном путевом листе может быть только один RETURN.")

        previous_record = get_previous_waybill_record(
            waybill=self.waybill,
            timestamp=timestamp,
            current_instance=current_instance,
        )
        next_record = get_next_waybill_record(
            waybill=self.waybill,
            timestamp=timestamp,
            current_instance=current_instance,
        )

        transition_error = validate_transition(
            previous_record=previous_record,
            current_code=event_type,
            current_kind="event",
        )
        if transition_error:
            raise forms.ValidationError(transition_error)

        next_transition_error = validate_next_transition(
            current_code=event_type,
            current_kind="event",
            next_record=next_record,
        )
        if next_transition_error:
            raise forms.ValidationError(next_transition_error)

        if previous_record and previous_record.odometer is not None and odometer < previous_record.odometer:
            raise forms.ValidationError(
                f"Показание одометра ({odometer}) не может быть меньше предыдущего "
                f"значения ({previous_record.odometer}) от {previous_record.timestamp:%d.%m.%Y %H:%M}."
            )

        if next_record and next_record.odometer is not None and odometer > next_record.odometer:
            raise forms.ValidationError(
                f"Показание одометра ({odometer}) не может быть больше следующего "
                f"значения ({next_record.odometer}) от {next_record.timestamp:%d.%m.%Y %H:%M}."
            )

        return cleaned_data


class RoutePointForm(BaseStyledModelForm):
    trip = AjaxModelChoiceField(
        queryset=Trip.objects.none(),
        label="Рейс",
        required=False,
    )

    class Meta:
        model = RoutePoint
        fields = [
            "point_type",
            "timestamp",
            "address",
            "odometer",
            "trip",
        ]
        widgets = {
            "point_type": forms.Select(),
            "timestamp": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                },
                format="%Y-%m-%dT%H:%M",
            ),
            "address": forms.TextInput(
                attrs={
                    "placeholder": "Адрес точки",
                }
            ),
            "odometer": forms.NumberInput(
                attrs={
                    "min": 0,
                    "step": 1,
                    "placeholder": "Показание одометра",
                }
            ),
        }

    def __init__(self, *args, account=None, **kwargs):
        self.waybill = kwargs.pop("waybill", None)
        super().__init__(*args, **kwargs)

        if not self.instance.pk and "timestamp" in self.fields:
            self.fields["timestamp"].initial = timezone.localtime().strftime("%Y-%m-%dT%H:%M")

        if account:
            trip_field = self.fields["trip"]
            full_qs = Trip.objects.filter(account=account)
            trip_field._validation_qs = full_qs
            current_trip = getattr(self.instance, "trip", None)
            if current_trip and current_trip.pk:
                trip_field.queryset = full_qs.filter(pk=current_trip.pk)
            trip_field.widget.attrs["data-search-url"] = reverse("trips:search")

    def clean_odometer(self):
        value = self.cleaned_data["odometer"]
        if value is None:
            raise forms.ValidationError("Показание одометра обязательно.")
        if value < 0:
            raise forms.ValidationError("Показание одометра не может быть отрицательным.")
        return value

    def clean(self):
        cleaned_data = super().clean()

        if self.waybill and getattr(self.waybill, "status", None) == Waybill.Status.CLOSED:
            raise forms.ValidationError("Путевой лист закрыт. Добавление маршрутных точек запрещено.")

        point_type = cleaned_data.get("point_type")
        timestamp = cleaned_data.get("timestamp")
        odometer = cleaned_data.get("odometer")

        if point_type and point_type not in ("LOAD", "UNLOAD"):
            self.add_error("point_type", "Допустимы только: LOAD, UNLOAD.")

        if not timestamp:
            self.add_error("timestamp", "Дата и время обязательны.")

        if not self.waybill or not point_type or not timestamp or odometer is None:
            return cleaned_data

        current_instance = self.instance if self.instance.pk else None

        previous_record = get_previous_waybill_record(
            waybill=self.waybill,
            timestamp=timestamp,
            current_instance=current_instance,
        )
        next_record = get_next_waybill_record(
            waybill=self.waybill,
            timestamp=timestamp,
            current_instance=current_instance,
        )

        transition_error = validate_transition(
            previous_record=previous_record,
            current_code=point_type,
            current_kind="route_point",
        )
        if transition_error:
            raise forms.ValidationError(transition_error)

        next_transition_error = validate_next_transition(
            current_code=point_type,
            current_kind="route_point",
            next_record=next_record,
        )
        if next_transition_error:
            raise forms.ValidationError(next_transition_error)

        if previous_record and previous_record.odometer is not None and odometer < previous_record.odometer:
            raise forms.ValidationError(
                f"Показание одометра ({odometer}) не может быть меньше предыдущего "
                f"значения ({previous_record.odometer}) от {previous_record.timestamp:%d.%m.%Y %H:%M}."
            )

        if next_record and next_record.odometer is not None and odometer > next_record.odometer:
            raise forms.ValidationError(
                f"Показание одометра ({odometer}) не может быть больше следующего "
                f"значения ({next_record.odometer}) от {next_record.timestamp:%d.%m.%Y %H:%M}."
            )

        return cleaned_data