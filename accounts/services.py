from django.contrib.auth.models import User
from django.db import transaction

from organizations.models import Organization

from .models import Account, UserProfile


@transaction.atomic
def register_account_with_owner(
    *,
    company_name: str,
    inn: str,
    email: str,
    password: str,
) -> User:
    """
    Регистрирует новый tenant:
    - User (username=email)
    - Account (owner=user)
    - UserProfile (account + role=owner)
    - Первая "собственная" Organization
    """
    normalized_email = email.strip().lower()
    normalized_company_name = company_name.strip()

    user = User.objects.create_user(
        username=normalized_email,
        email=normalized_email,
        password=password,
    )

    account = Account.objects.create(
        name=normalized_company_name,
        owner=user,
    )

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.account = account
    profile.role = UserProfile.Role.OWNER
    profile.save(update_fields=["account", "role"])

    Organization.objects.create(
        created_by=user,
        account=account,
        full_name=normalized_company_name,
        short_name=normalized_company_name,
        inn=inn.strip(),
        ogrn=None,
        is_own_company=True,
    )

    return user


@transaction.atomic
def create_account_user_by_admin(
    *,
    account: Account,
    created_by: User,
    email: str,
    password: str,
    role: str,
    first_name: str = "",
    last_name: str = "",
) -> User:
    """
    Создание пользователя внутри текущего account.
    account всегда берётся из контекста текущего пользователя (не из формы).
    """
    normalized_email = email.strip().lower()

    user = User.objects.create_user(
        username=normalized_email,
        email=normalized_email,
        password=password,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
    )

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.account = account
    profile.role = role
    profile.save(update_fields=["account", "role"])

    return user
