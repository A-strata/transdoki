from itertools import chain

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Max
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from transdoki.tenancy import get_request_account

from .forms import RoutePointForm, WaybillEventForm, WaybillForm
from .models import Waybill, WaybillEvent


def build_waybill_timeline(waybill):
    """
    Объединяет события и маршрутные точки в одну хронологию.
    """
    events = waybill.events.all()
    route_points = waybill.route_points.all()

    timeline = []

    for item in chain(events, route_points):
        if isinstance(item, WaybillEvent):
            timeline.append(
                {
                    "kind": "event",
                    "timestamp": item.timestamp,
                    "obj": item,
                    "type": item.event_type,
                    "label": item.get_event_type_display(),
                    "odometer": item.odometer,
                    "address": "",
                }
            )
        else:
            timeline.append(
                {
                    "kind": "route_point",
                    "timestamp": item.timestamp,
                    "obj": item,
                    "type": item.point_type,
                    "label": item.get_point_type_display(),
                    "odometer": item.odometer,
                    "address": item.address,
                    "sequence": item.sequence,
                    "trip": item.trip,
                }
            )

    timeline.sort(key=lambda x: (x["timestamp"], 0 if x["kind"] == "event" else 1))
    return timeline


class WaybillListView(LoginRequiredMixin, ListView):
    model = Waybill
    template_name = "waybills/waybill_list.html"
    context_object_name = "waybills"
    paginate_by = 20

    def get_queryset(self):
        qs = (
            Waybill.objects.for_account(get_request_account(self.request))
            .select_related("organization", "driver", "truck", "trailer")
            .order_by("-date", "-id")
        )
        status = self.request.GET.get("status")
        if status in (Waybill.Status.OPEN, Waybill.Status.CLOSED):
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_filter"] = self.request.GET.get("status", "")
        return context


class WaybillCreateView(LoginRequiredMixin, CreateView):
    model = Waybill
    form_class = WaybillForm
    template_name = "waybills/waybill_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["account"] = get_request_account(self.request)
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.account = get_request_account(self.request)

        response = super().form_valid(form)
        messages.success(self.request, "Путевой лист успешно создан.")
        return response

    def get_success_url(self):
        return reverse("waybills:waybill-detail", kwargs={"pk": self.object.pk})


class WaybillUpdateView(LoginRequiredMixin, UpdateView):
    model = Waybill
    form_class = WaybillForm
    template_name = "waybills/waybill_form.html"
    context_object_name = "waybill"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["account"] = get_request_account(self.request)
        return kwargs

    def get_queryset(self):
        return Waybill.objects.for_account(
            get_request_account(self.request)
        ).select_related("driver", "truck", "trailer")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Шапка путевого листа обновлена.")
        return response

    def get_success_url(self):
        return reverse("waybills:waybill-detail", kwargs={"pk": self.object.pk})


class WaybillDetailView(LoginRequiredMixin, DetailView):
    model = Waybill
    template_name = "waybills/waybill_detail.html"
    context_object_name = "waybill"

    def get_queryset(self):
        return (
            Waybill.objects.for_account(get_request_account(self.request))
            .select_related("driver", "truck", "trailer")
            .prefetch_related("events", "route_points__trip")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        waybill = self.object

        account = get_request_account(self.request)
        context.setdefault("event_form", WaybillEventForm(waybill=waybill))
        context.setdefault("route_point_form", RoutePointForm(waybill=waybill, account=account))
        context["timeline"] = build_waybill_timeline(waybill)
        context["is_closed"] = getattr(waybill, "status", None) == Waybill.Status.CLOSED

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action")

        if getattr(self.object, "status", None) == Waybill.Status.CLOSED:
            messages.error(
                request, "Путевой лист закрыт. Добавление записей запрещено."
            )
            return redirect("waybills:waybill-detail", pk=self.object.pk)

        if action == "add_event":
            return self.handle_add_event()
        elif action == "add_route_point":
            return self.handle_add_route_point()

        messages.error(request, "Неизвестное действие.")
        return redirect("waybills:waybill-detail", pk=self.object.pk)

    def handle_add_event(self):
        form = WaybillEventForm(self.request.POST, waybill=self.object)

        if form.is_valid():
            event = form.save(commit=False)
            event.waybill = self.object
            event.save()

            messages.success(self.request, "Событие добавлено.")
            return redirect("waybills:waybill-detail", pk=self.object.pk)

        context = self.get_context_data(
            event_form=form,
            route_point_form=RoutePointForm(waybill=self.object, account=get_request_account(self.request)),
        )
        return self.render_to_response(context)

    def handle_add_route_point(self):
        form = RoutePointForm(self.request.POST, waybill=self.object, account=get_request_account(self.request))

        if form.is_valid():
            route_point = form.save(commit=False)
            route_point.waybill = self.object
            route_point.sequence = self.get_next_route_point_sequence()
            route_point.save()

            messages.success(self.request, "Маршрутная точка добавлена.")
            return redirect("waybills:waybill-detail", pk=self.object.pk)

        context = self.get_context_data(
            event_form=WaybillEventForm(waybill=self.object),
            route_point_form=form,
        )
        return self.render_to_response(context)

    def get_next_route_point_sequence(self):
        max_sequence = self.object.route_points.aggregate(max_seq=Max("sequence"))[
            "max_seq"
        ]
        return (max_sequence or 0) + 1


class WaybillFormV2View(LoginRequiredMixin, TemplateView):
    """Экспериментальный шаблон формы путевого листа (только UI)."""

    template_name = "waybills/waybill_form_v2.html"
