from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import ProtectedError, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView

from accounts.models import UserProfile
from billing.mixins import ModuleRequiredMixin
from transdoki.tenancy import get_request_account
from transdoki.views import UserOwnedListView

from . import services
from .forms import ContractAttachmentForm, ContractForm, TemplateUploadForm
from .models import Contract, ContractAttachment, ContractTemplate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user_can_edit(user):
    """owner и admin могут создавать/редактировать/удалять."""
    role = getattr(getattr(user, "profile", None), "role", None)
    return role in {UserProfile.Role.OWNER, UserProfile.Role.ADMIN}


class ContractsModuleMixin(ModuleRequiredMixin):
    """Доступ к разделу «Договоры» только при подключённом модуле."""

    required_module = "contracts"


class EditPermissionMixin:
    """Проверяет, что пользователь owner или admin."""

    def dispatch(self, request, *args, **kwargs):
        if not _user_can_edit(request.user):
            messages.error(request, "У вас нет прав для этого действия.")
            return redirect("contracts:list")
        return super().dispatch(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Contract CRUD
# ---------------------------------------------------------------------------


CONTRACT_SORT_FIELDS = ("date_signed", "number", "contractor__short_name")


class ContractListView(ContractsModuleMixin, UserOwnedListView):
    model = Contract
    template_name = "contracts/contract_list.html"
    partial_template_name = "contracts/contract_list_table.html"
    context_object_name = "contracts"
    paginate_by = 25
    page_size_options = [25, 50, 100]

    def get_template_names(self):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return [self.partial_template_name]
        return [self.template_name]

    def _parse_sort(self):
        sort_field = self.request.GET.get("sort", "date_signed").strip()
        sort_dir = self.request.GET.get("dir", "desc").strip()
        if sort_field not in CONTRACT_SORT_FIELDS:
            sort_field = "date_signed"
        if sort_dir not in ("asc", "desc"):
            sort_dir = "desc"
        return sort_field, sort_dir

    def get_queryset(self):
        qs = super().get_queryset().select_related("own_company", "contractor")

        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(number__icontains=q) | Q(contractor__short_name__icontains=q)
            )

        status = self.request.GET.get("status")
        if status and status in dict(Contract.STATUS_CHOICES):
            qs = qs.filter(status=status)

        sort_field, sort_dir = self._parse_sort()
        order = sort_field if sort_dir == "asc" else f"-{sort_field}"
        return qs.order_by(order, "-pk")

    def _build_sort_url(self, field, current_sort, current_dir, base_params):
        params = dict(base_params)
        params["sort"] = field
        params["dir"] = (
            "desc" if (field == current_sort and current_dir == "asc") else "asc"
        )
        return "?" + urlencode(params)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        page_obj = ctx.get("page_obj")
        ctx["pagination_items"] = (
            self._build_pagination_items(page_obj) if page_obj else []
        )
        ctx["page_size_options"] = self.page_size_options

        q = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "")
        sort_field, sort_dir = self._parse_sort()
        current_page_size = self.get_paginate_by(self.object_list)

        if q:
            base_qs = super().get_queryset()
            if status and status in dict(Contract.STATUS_CHOICES):
                base_qs = base_qs.filter(status=status)
            ctx["total_count"] = base_qs.count()

        ctx["status_choices"] = Contract.STATUS_CHOICES
        ctx["filters"] = {
            "q": q,
            "status": status,
            "sort": sort_field,
            "dir": sort_dir,
            "page_size": str(current_page_size),
        }

        base_params = {}
        if q:
            base_params["q"] = q
        if status:
            base_params["status"] = status
        if sort_field != "date_signed":
            base_params["sort"] = sort_field
        if sort_dir != "desc":
            base_params["dir"] = sort_dir
        if str(current_page_size) != str(self.paginate_by):
            base_params["page_size"] = current_page_size
        ctx["query_string"] = ("&" + urlencode(base_params)) if base_params else ""

        ctx["sort_urls"] = {
            f: self._build_sort_url(f, sort_field, sort_dir, base_params)
            for f in CONTRACT_SORT_FIELDS
        }

        return ctx


class ContractDetailView(ContractsModuleMixin, LoginRequiredMixin, DetailView):
    model = Contract
    template_name = "contracts/contract_detail.html"

    def get_queryset(self):
        return (
            Contract.objects.for_account(get_request_account(self.request))
            .select_related("own_company", "contractor")
            .prefetch_related("attachments")
        )


class ContractCreateView(
    ContractsModuleMixin,
    EditPermissionMixin,
    LoginRequiredMixin,
    CreateView,
):
    model = Contract
    form_class = ContractForm
    template_name = "contracts/contract_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.account = get_request_account(self.request)
        self.object = form.save()
        messages.success(self.request, f"Договор №{self.object.number} создан.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("contracts:detail", kwargs={"pk": self.object.pk})


class ContractUpdateView(
    ContractsModuleMixin,
    EditPermissionMixin,
    LoginRequiredMixin,
    UpdateView,
):
    model = Contract
    form_class = ContractForm
    template_name = "contracts/contract_form.html"

    def get_queryset(self):
        return Contract.objects.for_account(get_request_account(self.request))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        self.object = form.save()
        messages.success(self.request, "Договор сохранён.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("contracts:detail", kwargs={"pk": self.object.pk})


class ContractDeleteView(
    ContractsModuleMixin,
    EditPermissionMixin,
    LoginRequiredMixin,
    DeleteView,
):
    model = Contract
    template_name = "contracts/contract_confirm_delete.html"
    success_url = reverse_lazy("contracts:list")

    def get_queryset(self):
        return Contract.objects.for_account(get_request_account(self.request))

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            self.object.delete()
            messages.success(request, f"Договор №{self.object.number} удалён.")
            return redirect(self.success_url)
        except ProtectedError:
            messages.error(request, "Невозможно удалить: есть связанные данные.")
            return redirect(reverse("contracts:detail", kwargs={"pk": self.object.pk}))


# ---------------------------------------------------------------------------
# Contract download
# ---------------------------------------------------------------------------


class ContractDownloadView(ContractsModuleMixin, LoginRequiredMixin, View):
    def get(self, request, pk):
        contract = get_object_or_404(
            Contract.objects.select_related(
                "own_company",
                "contractor",
            ),
            pk=pk,
            account=get_request_account(request),
        )
        return services.generate_contract_response(contract)


# ---------------------------------------------------------------------------
# ContractAttachment CRUD
# ---------------------------------------------------------------------------


class AttachmentCreateView(
    ContractsModuleMixin,
    EditPermissionMixin,
    LoginRequiredMixin,
    CreateView,
):
    model = ContractAttachment
    form_class = ContractAttachmentForm
    template_name = "contracts/attachment_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.contract = get_object_or_404(
            Contract.objects.for_account(get_request_account(request)),
            pk=kwargs["contract_pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["contract"] = self.contract
        return ctx

    def form_valid(self, form):
        form.instance.contract = self.contract
        form.instance.created_by = self.request.user
        form.instance.account = self.contract.account
        self.object = form.save()
        messages.success(
            self.request,
            f"{self.object.get_attachment_type_display()} №{self.object.number} создано.",
        )
        return redirect(reverse("contracts:detail", kwargs={"pk": self.contract.pk}))


class AttachmentDownloadView(ContractsModuleMixin, LoginRequiredMixin, View):
    def get(self, request, pk):
        attachment = get_object_or_404(
            ContractAttachment.objects.select_related(
                "contract__own_company",
                "contract__contractor",
            ),
            pk=pk,
            contract__account=get_request_account(request),
        )
        return services.generate_attachment_response(attachment)


class AttachmentDeleteView(
    ContractsModuleMixin,
    EditPermissionMixin,
    LoginRequiredMixin,
    View,
):
    def post(self, request, pk):
        attachment = get_object_or_404(
            ContractAttachment,
            pk=pk,
            contract__account=get_request_account(request),
        )
        contract_pk = attachment.contract_id
        label = f"{attachment.get_attachment_type_display()} №{attachment.number}"
        attachment.delete()
        messages.success(request, f"{label} удалено.")
        return redirect(reverse("contracts:detail", kwargs={"pk": contract_pk}))


# ---------------------------------------------------------------------------
# Template management
# ---------------------------------------------------------------------------


TEMPLATE_META = {
    "transport_contract": {
        "badge": "Рамочный",
        "section": "transport",
        "parent": None,
    },
    "transport_request": {
        "badge": "Дочерний",
        "section": "transport",
        "parent": "transport_contract",
    },
    "single_transport": {
        "badge": "Самостоятельный",
        "section": "transport",
        "parent": None,
    },
    "order_request": {
        "badge": "Самостоятельный",
        "section": "transport",
        "parent": None,
    },
    "supply_contract": {
        "badge": "Рамочный",
        "section": "supply",
        "parent": None,
    },
    "supply_spec": {
        "badge": "Дочерний",
        "section": "supply",
        "parent": "supply_contract",
    },
}

SECTIONS = [
    ("transport", "Перевозки"),
    ("supply", "Поставки"),
]


class TemplateSettingsView(
    ContractsModuleMixin,
    EditPermissionMixin,
    LoginRequiredMixin,
    View,
):
    def get(self, request):
        account = get_request_account(request)
        uploaded = {
            ct.template_type: ct
            for ct in ContractTemplate.objects.filter(account=account)
        }

        items = []
        for code, label in ContractTemplate.TEMPLATE_TYPE_CHOICES:
            ct = uploaded.get(code)
            meta = TEMPLATE_META.get(code, {})
            items.append({
                "code": code,
                "label": label,
                "uploaded": ct,
                "badge": meta.get("badge", ""),
                "section": meta.get("section", ""),
                "is_child": meta.get("parent") is not None,
                "placeholders": services.PLACEHOLDERS.get(code, []),
            })

        from django.shortcuts import render

        return render(request, "contracts/template_settings.html", {
            "items": items,
            "sections": SECTIONS,
        })


class TemplateUploadView(
    ContractsModuleMixin,
    EditPermissionMixin,
    LoginRequiredMixin,
    View,
):
    def post(self, request, template_type):
        valid_types = dict(ContractTemplate.TEMPLATE_TYPE_CHOICES)
        if template_type not in valid_types:
            messages.error(request, "Неизвестный тип шаблона.")
            return redirect("contracts:template_settings")

        form = TemplateUploadForm(request.POST, request.FILES)
        if form.is_valid():
            account = get_request_account(request)
            services.replace_template(
                account,
                template_type,
                form.cleaned_data["file"],
                request.user,
            )
            messages.success(
                request,
                f"Шаблон «{valid_types[template_type]}» загружен.",
            )
        else:
            for err in form.errors.values():
                messages.error(request, err[0])
        return redirect("contracts:template_settings")


class TemplateDeleteView(
    ContractsModuleMixin,
    EditPermissionMixin,
    LoginRequiredMixin,
    View,
):
    def post(self, request, template_type):
        valid_types = dict(ContractTemplate.TEMPLATE_TYPE_CHOICES)
        if template_type not in valid_types:
            messages.error(request, "Неизвестный тип шаблона.")
            return redirect("contracts:template_settings")

        account = get_request_account(request)
        services.delete_template(account, template_type)
        messages.success(
            request,
            f"Шаблон «{valid_types[template_type]}» удалён. Используется дефолтный.",
        )
        return redirect("contracts:template_settings")


class TemplateDownloadDefaultView(ContractsModuleMixin, LoginRequiredMixin, View):
    def get(self, request, template_type):
        valid_types = dict(ContractTemplate.TEMPLATE_TYPE_CHOICES)
        if template_type not in valid_types:
            messages.error(request, "Неизвестный тип шаблона.")
            return redirect("contracts:template_settings")

        path = services._get_default_template_path(template_type)
        if not path.exists():
            messages.error(request, "Дефолтный шаблон не найден.")
            return redirect("contracts:template_settings")

        return FileResponse(
            open(path, "rb"),
            as_attachment=True,
            filename=f"{valid_types[template_type]} (шаблон).docx",
            content_type=(
                "application/vnd.openxmlformats-"
                "officedocument.wordprocessingml.document"
            ),
        )
