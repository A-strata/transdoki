from django import forms

from vehicles.models import Vehicle

from .models import Organization


class OrganizationForm(forms.ModelForm):
    petrolplus_client_secret = forms.CharField(
        required=False,
        label="PetrolPlus Client Secret",
        widget=forms.PasswordInput(
            render_value=False,
            attrs={
                "autocomplete": "new-password",
                "placeholder": "Введите новый secret",
            },
        ),
    )

    class Meta:
        model = Organization
        fields = [
            "inn",
            "full_name",
            "short_name",
            "ogrn",
            "kpp",
            "address",
            "is_own_company",
            "petrolplus_integration_enabled",
            "petrolplus_client_id",
            "petrolplus_client_secret",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Показываем PetrolPlus только для уже сохранённой "своей компании"
        self.show_petrolplus_fields = bool(
            self.instance.pk and self.instance.is_own_company
        )
        self.fields["petrolplus_integration_enabled"].widget.attrs.update(
            {"class": "toggle-input"}
        )

    def _resolve_show_petrolplus_fields(self) -> bool:
        if self.is_bound:
            raw = self.data.get(self.add_prefix("is_own_company"))
            return raw in ("on", "1", "true", "True")
        return bool(getattr(self.instance, "is_own_company", False))

    def clean(self):
        cleaned_data = super().clean()

        is_own_company = cleaned_data.get("is_own_company")
        integration_enabled = cleaned_data.get("petrolplus_integration_enabled")
        client_id = cleaned_data.get("petrolplus_client_id")
        secret_input = cleaned_data.get("petrolplus_client_secret")

        # Не своя компания -> интеграцию выключаем и креды очищаем
        if not is_own_company:
            cleaned_data["petrolplus_integration_enabled"] = False
            cleaned_data["petrolplus_client_id"] = None
            cleaned_data["petrolplus_client_secret"] = None
            return cleaned_data

        # Своя компания + включена интеграция -> client_id обязателен
        if integration_enabled and not client_id:
            self.add_error("petrolplus_client_id", "Укажите PetrolPlus Client ID.")

        # Для create secret обязателен, если интеграция включена.
        # Для update можно оставить пустым, чтобы сохранить существующий.
        has_existing_secret = bool(
            self.instance.pk and self.instance.petrolplus_client_secret
        )
        if integration_enabled and not secret_input and not has_existing_secret:
            self.add_error(
                "petrolplus_client_secret", "Укажите PetrolPlus Client Secret."
            )

        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)

        # Если update и secret не ввели — оставляем прежний
        new_secret = self.cleaned_data.get("petrolplus_client_secret")
        if obj.pk and not new_secret:
            old = (
                Organization.objects.filter(pk=obj.pk)
                .only("petrolplus_client_secret")
                .first()
            )
            if old:
                obj.petrolplus_client_secret = old.petrolplus_client_secret

        if commit:
            obj.save()
        return obj


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["grn", "brand", "model", "vehicle_type", "property_type"]


VehicleFormSet = forms.inlineformset_factory(
    Organization,
    Vehicle,
    form=VehicleForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=True,
)
