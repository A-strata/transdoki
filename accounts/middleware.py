from datetime import timedelta

from django.utils import timezone

# Обновляем last_activity не чаще одного раза в 5 минут,
# чтобы не писать в БД на каждый запрос.
_UPDATE_INTERVAL = timedelta(minutes=5)


class CurrentOrganizationMiddleware:
    """
    Устанавливает request.current_org — текущую выбранную организацию пользователя
    (is_own_company=True). Хранится в session["current_org_id"].
    Если значение в сессии невалидно — подставляет первую свою организацию.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.current_org = None

        if request.user.is_authenticated:
            self._set_current_org(request)

        return self.get_response(request)

    def _set_current_org(self, request):
        from organizations.models import Organization
        from transdoki.tenancy import get_request_account

        account = get_request_account(request)
        own_orgs = Organization.objects.filter(
            account=account, is_own_company=True
        ).order_by("short_name")
        request.own_orgs = own_orgs

        session_org_id = request.session.get("current_org_id")
        org = None

        if session_org_id:
            org = own_orgs.filter(pk=session_org_id).first()

        if org is None:
            org = own_orgs.first()
            if org is not None and session_org_id != org.pk:
                request.session["current_org_id"] = org.pk

        request.current_org = org


class SessionActivityMiddleware:
    """
    Обновляет last_activity для текущей UserSession пользователя.
    Запись в БД происходит не чаще чем раз в _UPDATE_INTERVAL.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if (
            request.user.is_authenticated
            and hasattr(request, "session")
            and request.session.session_key
        ):
            self._maybe_update_session(request)

        return response

    def _maybe_update_session(self, request):
        from accounts.models import UserSession

        now = timezone.now()
        stale_threshold = now - _UPDATE_INTERVAL

        UserSession.objects.filter(
            user=request.user,
            session_key=request.session.session_key,
            is_active=True,
            last_activity__lt=stale_threshold,
        ).update(last_activity=now)
