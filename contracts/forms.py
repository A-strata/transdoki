import zipfile

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
                # Используем tenant-менеджер вместо .filter — см. CLAUDE.md.
                self.fields["own_company"].queryset = Organization.objects.own_for(
                    account_id
                )
                self.fields["contractor"].queryset = (
                    Organization.objects.for_account(account_id)
                    .filter(is_own_company=False)
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
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)


class TemplateUploadForm(forms.Form):
    file = forms.FileField(label="Файл шаблона (.docx)")

    MAX_FILE_SIZE = 5 * 1024 * 1024

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith(".docx"):
            raise forms.ValidationError("Допускаются только файлы формата .docx")
        if f.size > self.MAX_FILE_SIZE:
            raise forms.ValidationError("Максимальный размер файла — 5 МБ")

        # Строгая проверка: DOCX — это ZIP-архив с word/document.xml.
        # Не даёт загрузить произвольный бинарь с расширением .docx.
        try:
            f.seek(0)
            with zipfile.ZipFile(f) as zf:
                if "word/document.xml" not in zf.namelist():
                    raise forms.ValidationError(
                        "Файл не является корректным DOCX: внутри не найдена "
                        "word/document.xml. Сохраните документ в Word как .docx."
                    )
        except zipfile.BadZipFile as exc:
            raise forms.ValidationError(
                "Файл повреждён или не является DOCX."
            ) from exc
        finally:
            # Вернём указатель в начало, иначе Django сохранит файл не с нуля.
            try:
                f.seek(0)
            except Exception:
                pass

        return f
