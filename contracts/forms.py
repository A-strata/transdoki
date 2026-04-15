from django import forms

from organizations.models import Organization
from transdoki.forms import ErrorHighlightMixin

from .models import Contract, ContractAttachment


class ContractForm(ErrorHighlightMixin, forms.ModelForm):
    class Meta:
        model = Contract
        fields = [
            "number",
            "contract_type",
            "status",
            "own_company",
            "contractor",
            "date_signed",
            "valid_until",
            "amount",
            "subject",
            "notes",
        ]
        widgets = {
            "date_signed": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
            "valid_until": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
            "subject": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)

        if self.user and self.user.is_authenticated:
            account_id = getattr(
                getattr(self.user, "profile", None), "account_id", None
            )
            if account_id:
                all_orgs = Organization.objects.filter(account_id=account_id)
                self.fields["own_company"].queryset = Organization.objects.own_for(
                    account_id
                )
                self.fields["contractor"].queryset = all_orgs.filter(
                    is_own_company=False
                )


class ContractAttachmentForm(ErrorHighlightMixin, forms.ModelForm):
    class Meta:
        model = ContractAttachment
        fields = [
            "attachment_type",
            "number",
            "date_signed",
            "amount",
            "subject",
            "notes",
        ]
        widgets = {
            "date_signed": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
            "subject": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        kwargs.pop("user", None)
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)


class TemplateUploadForm(forms.Form):
    file = forms.FileField(label="Файл шаблона (.docx)")

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith(".docx"):
            raise forms.ValidationError("Допускаются только файлы формата .docx")
        if f.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Максимальный размер файла — 5 МБ")
        return f
