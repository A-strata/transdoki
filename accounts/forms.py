from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from organizations.models import Organization
from organizations.validators import validate_inn

from .services import register_account_with_owner


class AccountRegistrationForm(forms.Form):
    company_name = forms.CharField(
        label="Название компании",
        max_length=200,
    )
    inn = forms.CharField(
        label="ИНН",
        max_length=12,
        validators=[validate_inn],
    )
    email = forms.EmailField(
        label="Email",
    )
    password1 = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label="Подтверждение пароля",
        widget=forms.PasswordInput,
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(username__iexact=email).exists():
            raise ValidationError("Пользователь с таким email уже существует.")

        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Email уже используется.")

        return email

    def clean_inn(self):
        inn = self.cleaned_data["inn"].strip()

        # Глобальная проверка бизнес-правила для own company
        if Organization.objects.filter(inn=inn, is_own_company=True).exists():
            raise ValidationError(
                "Собственная компания с таким ИНН уже существует в системе."
            )

        return inn

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Пароли не совпадают.")
            return cleaned_data

        if password1:
            validate_password(password1)

        return cleaned_data

    def save(self):
        return register_account_with_owner(
            company_name=self.cleaned_data["company_name"],
            inn=self.cleaned_data["inn"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
        )
