import re
import secrets
import string

from django.contrib.auth.models import User
from django.db import transaction

from organizations.models import Organization

from .models import Account, UserProfile

_TRANSLIT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh',
    'з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o',
    'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts',
    'ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
}


def _transliterate(text: str) -> str:
    return ''.join(_TRANSLIT.get(c, c) for c in text.lower())


def _generate_username(first_name: str, last_name: str, exclude_pk: int | None = None) -> str:
    last = re.sub(r'[^a-z0-9]', '', _transliterate(last_name))
    first_init = re.sub(r'[^a-z0-9]', '', _transliterate(first_name[:1])) if first_name else ''
    base = f"{last}.{first_init}" if first_init else last or 'user'
    username = base
    counter = 2
    qs = User.objects.all() if exclude_pk is None else User.objects.exclude(pk=exclude_pk)
    while qs.filter(username=username).exists():
        username = f"{base}{counter}"
        counter += 1
    return username


def _generate_temp_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@transaction.atomic
def register_account_with_owner(
    *,
    first_name: str,
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
        first_name=first_name.strip(),
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


def reset_account_user_password(*, profile, actor) -> str:
    """
    Сбрасывает логин и пароль пользователя до заводских значений.
    Логин перегенерируется по имени/фамилии, пароль — случайная строка.
    actor — пользователь, инициирующий сброс (owner/admin).
    Возвращает temp_password.
    """
    user = profile.user
    new_username = _generate_username(user.first_name, user.last_name, exclude_pk=user.pk)
    temp_password = _generate_temp_password()
    user.username = new_username
    user.set_password(temp_password)
    user.save(update_fields=["username", "password"])
    return temp_password


@transaction.atomic
def create_account_user_by_admin(
    *,
    account: Account,
    created_by: User,
    first_name: str,
    last_name: str,
    role: str,
) -> tuple:
    """
    Создание пользователя внутри текущего account.
    Логин генерируется автоматически (фамилия.инициал),
    временный пароль — случайная строка.
    Возвращает (user, temp_password).
    """
    username = _generate_username(first_name, last_name)
    temp_password = _generate_temp_password()

    user = User.objects.create_user(
        username=username,
        email="",
        password=temp_password,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
    )

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.account = account
    profile.role = role
    profile.save(update_fields=["account", "role"])

    return user, temp_password
