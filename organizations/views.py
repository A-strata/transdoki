from django.views.generic import CreateView
from django.urls import reverse_lazy
from .models import Organization
from .forms import OrganizationForm

class OrganizationCreateView(CreateView):
    model = Organization
    form_class = OrganizationForm
    template_name = 'organizations/organization_form.html'
    success_url = reverse_lazy('organizations:list')

