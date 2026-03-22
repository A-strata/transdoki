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
        ogrn=None,  # теперь допустимо (null=True, blank=True)
        is_own_company=True,
    )

    return user
