from django.views.generic import CreateView, ListView
from django.urls import reverse_lazy
from .models import Organization
from .forms import OrganizationForm

class OrganizationCreateView(CreateView):
    model = Organization
    form_class = OrganizationForm
    template_name = 'organizations/organization_form.html'
    success_url = reverse_lazy('organizations:list')

class OrganizationListView(ListView):
    model = Organization
    template_name = 'organizations/organization_list.html'
    context_object_name = 'organizations'  # опционально, для ясности в шаблоне