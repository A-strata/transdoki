from itertools import chain

from django.contrib import messages
from django.db.models import Max
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, UpdateView, DetailView, ListView

from .forms import WaybillForm, WaybillEventForm, RoutePointForm
from .models import Waybill, WaybillEvent, RoutePoint


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
                }
            )

    timeline.sort(key=lambda x: (x["timestamp"], 0 if x["kind"] == "event" else 1))
    return timeline


class WaybillListView(ListView):
    model = Waybill
    template_name = "waybills/waybill_list.html"
    context_object_name = "waybills"
    paginate_by = 20

    def get_queryset(self):
        return (
            Waybill.objects
            .select_related("driver", "truck", "trailer")
            .order_by("-date", "-id")
        )


class WaybillCreateView(CreateView):
    model = Waybill
    form_class = WaybillForm
    template_name = "waybills/waybill_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Путевой лист успешно создан.")
        return response

    def get_success_url(self):
        return reverse("waybills:waybill-detail", kwargs={"pk": self.object.pk})


class WaybillUpdateView(UpdateView):
    model = Waybill
    form_class = WaybillForm
    template_name = "waybills/waybill_form.html"
    context_object_name = "waybill"

    def get_queryset(self):
        return (
            Waybill.objects
            .select_related("driver", "truck", "trailer")
        )

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Шапка путевого листа обновлена.")
        return response

    def get_success_url(self):
        return reverse("waybills:waybill-detail", kwargs={"pk": self.object.pk})


class WaybillDetailView(DetailView):
    model = Waybill
    template_name = "waybills/waybill_detail.html"
    context_object_name = "waybill"

    def get_queryset(self):
        return (
            Waybill.objects
            .select_related("driver", "truck", "trailer")
            .prefetch_related("events", "route_points")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        waybill = self.object

        context.setdefault("event_form", WaybillEventForm(waybill=waybill))
        context.setdefault("route_point_form", RoutePointForm(waybill=waybill))
        context["timeline"] = build_waybill_timeline(waybill)
        context["is_closed"] = getattr(waybill, "status", None) == Waybill.Status.CLOSED

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action")

        if getattr(self.object, "status", None) == Waybill.Status.CLOSED:
            messages.error(request, "Путевой лист закрыт. Добавление записей запрещено.")
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
            route_point_form=RoutePointForm(waybill=self.object),
        )
        return self.render_to_response(context)

    def handle_add_route_point(self):
        form = RoutePointForm(self.request.POST, waybill=self.object)

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
        max_sequence = self.object.route_points.aggregate(
            max_seq=Max("sequence")
        )["max_seq"]
        return (max_sequence or 0) + 1