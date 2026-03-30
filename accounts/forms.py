from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from organizations.models import Organization
from organizations.validators import validate_inn
from transdoki.forms import ErrorHighlightMixin

from .models import UserProfile
from .services import create_account_user_by_admin, register_account_with_owner


class AccountRegistrationForm(ErrorHighlightMixin, forms.Form):
    # Блок 1: О вас
    first_name = forms.CharField(
        label="Имя",
        max_length=150,
    )
    email = forms.EmailField(
        label="Email",
        max_length=150,
    )
    password1 = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(),
    )
    # Блок 2: О компании
    inn = forms.CharField(
        label="ИНН",
        max_length=12,
        validators=[validate_inn],
        widget=forms.HiddenInput(),
    )
    short_name = forms.CharField(
        label="Краткое наименование",
        max_length=200,
        widget=forms.HiddenInput(),
    )
    full_name = forms.CharField(
        label="Полное наименование",
        max_length=200,
        widget=forms.HiddenInput(),
    )
    kpp = forms.CharField(
        label="КПП",
        max_length=9,
        required=False,
        widget=forms.HiddenInput(),
    )
    ogrn = forms.CharField(
        label="ОГРН",
        max_length=15,
        required=False,
        widget=forms.HiddenInput(),
    )
    address = forms.CharField(
        label="Адрес",
        max_length=200,
        required=False,
        widget=forms.HiddenInput(),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip()

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

    def clean_password1(self):
        password = self.cleaned_data.get("password1")
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                raise ValidationError(e.messages)
        return password

    def save(self):
        return register_account_with_owner(
            first_name=self.cleaned_data["first_name"],
            short_name=self.cleaned_data["short_name"],
            full_name=self.cleaned_data["full_name"],
            inn=self.cleaned_data["inn"],
            kpp=self.cleaned_data.get("kpp") or None,
            ogrn=self.cleaned_data.get("ogrn") or None,
            address=self.cleaned_data.get("address") or None,
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
        )


class AccountUserCreateForm(ErrorHighlightMixin, forms.Form):
    ROLE_CHOICES = [
        (UserProfile.Role.ADMIN, "Администратор"),
        (UserProfile.Role.DISPATCHER, "Диспетчер"),
        (UserProfile.Role.LOGIST, "Логист"),
    ]

    last_name = forms.CharField(label="Фамилия", max_length=150)
    first_name = forms.CharField(label="Имя", max_length=150)
    role = forms.ChoiceField(label="Роль", choices=ROLE_CHOICES)

    def save(self, *, account, created_by):
        return create_account_user_by_admin(
            account=account,
            created_by=created_by,
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            role=self.cleaned_data["role"],
        )
