from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import WaybillCreateForm
from .models import Waybill
from .services import create_waybill


class WaybillCreateView(LoginRequiredMixin, CreateView):
    model = Waybill
    form_class = WaybillCreateForm
    template_name = 'waybills/waybill_form.html'

    def get_form_kwargs(self):
        # Передаём пользователя в форму,
        # чтобы ограничить выбор только его объектами.
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        # Создание выполняем через service,
        # а не через form.save().
        try:
            self.object = create_waybill(
                user=self.request.user,
                organization=form.cleaned_data['organization'],
                truck=form.cleaned_data['truck'],
                trailer=form.cleaned_data.get('trailer'),
                date=form.cleaned_data['date'],
            )
        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)

        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy('waybills:detail', kwargs={'pk': self.object.pk})
