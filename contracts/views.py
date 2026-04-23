from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import ProtectedError
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    TemplateView,
    UpdateView,
)

from accounts.models import UserProfile
from billing.mixins import ModuleRequiredMixin
from transdoki.tenancy import get_request_account
from transdoki.views import FilteredSortedListMixin, UserOwnedListView

from . import services
from .forms import ContractAttachmentForm, ContractForm, TemplateUploadForm
from .models import Contract, ContractAttachment, ContractTemplate
from .templates_registry import SECTIONS, TEMPLATES

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


class ContractListView(
    ContractsModuleMixin, FilteredSortedListMixin, UserOwnedListView
):
    model = Contract
    template_name = "contracts/contract_list.html"
    partial_template_name = "contracts/contract_list_table.html"
    context_object_name = "contracts"
    paginate_by = 25
    page_size_options = [25, 50, 100]

    search_fields = ("number", "contractor__short_name")
    sort_fields = ("date_signed", "number", "contractor__short_name")
    default_sort = "date_signed"
    default_sort_dir = "desc"

    def get_template_names(self):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return [self.partial_template_name]
        return [self.template_name]

    def _get_status_filter(self) -> str:
        status = self.request.GET.get("status", "")
        return status if status in dict(Contract.STATUS_CHOICES) else ""

    def apply_extra_filters(self, qs):
        status = self._get_status_filter()
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_extra_filter_params(self):
        status = self._get_status_filter()
        return {"status": status} if status else {}

    def get_queryset(self):
        qs = super().get_queryset().select_related("own_company", "contractor")
        return self.apply_filters_and_sort(qs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        page_obj = ctx.get("page_obj")
        ctx["pagination_items"] = (
            self._build_pagination_items(page_obj) if page_obj else []
        )

        # total_count нужен только при активном поиске — чтобы показать
        # "найдено X из Y" в нижней плашке. Без поиска Y == X, лишний запрос.
        if self.get_search_query():
            base_qs = Contract.objects.for_account(
                get_request_account(self.request)
            )
            status = self._get_status_filter()
            if status:
                base_qs = base_qs.filter(status=status)
            ctx["total_count"] = base_qs.count()

        ctx["status_choices"] = Contract.STATUS_CHOICES
        ctx.update(self.get_filter_context())
        # filters из миксина уже содержит status через get_extra_filter_params,
        # но при пустом статусе он не попадёт — шаблон ожидает всегда наличие
        # ключа (<option selected>), поэтому явно добавим.
        ctx["filters"].setdefault("status", "")
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
        try:
            return services.generate_contract_response(contract)
        except services.TemplateNotConfiguredError:
            messages.error(
                request,
                "Шаблон для этого типа договора не настроен. "
                "Загрузите свой шаблон в разделе «Шаблоны документов».",
            )
            return redirect(reverse("contracts:template_settings"))
        except services.DocGenerationError as exc:
            messages.error(request, f"Не удалось сгенерировать документ: {exc}")
            return redirect(reverse("contracts:detail", kwargs={"pk": pk}))


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
        try:
            return services.generate_attachment_response(attachment)
        except services.TemplateNotConfiguredError:
            messages.error(
                request,
                "Шаблон для этого типа приложения не настроен. "
                "Загрузите свой шаблон в разделе «Шаблоны документов».",
            )
            return redirect(reverse("contracts:template_settings"))
        except services.DocGenerationError as exc:
            messages.error(request, f"Не удалось сгенерировать документ: {exc}")
            return redirect(
                reverse("contracts:detail", kwargs={"pk": attachment.contract_id})
            )


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


class TemplateSettingsView(
    ContractsModuleMixin,
    EditPermissionMixin,
    LoginRequiredMixin,
    TemplateView,
):
    template_name = "contracts/template_settings.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        account = get_request_account(self.request)
        uploaded = {
            ct.template_type: ct
            for ct in ContractTemplate.objects.filter(account=account)
        }

        items = []
        for spec in TEMPLATES:
            items.append({
                "code": spec.code,
                "label": spec.template_label,
                "uploaded": uploaded.get(spec.code),
                "badge": spec.badge,
                "section": spec.section,
                "is_child": spec.parent is not None,
                "placeholders": services.PLACEHOLDERS.get(spec.code, []),
            })
        ctx["items"] = items
        ctx["sections"] = SECTIONS
        return ctx


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

        path = services.get_default_template_path(template_type)
        if not path.exists():
            messages.error(
                request,
                "Дефолтный шаблон для этого типа документа пока не поставляется. "
                "Загрузите свой файл через форму выше.",
            )
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
