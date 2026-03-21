from django.core.exceptions import PermissionDenied


def get_request_account(request):
    """
    Возвращает account текущего пользователя.
    Если account не найден — бросает PermissionDenied.
    """
    account = getattr(getattr(request.user, "profile", None), "account", None)
    if account is None:
        raise PermissionDenied("У пользователя не найден account.")
    return account
