import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

security_logger = logging.getLogger("security")
User = get_user_model()


class ImpersonationMiddleware:
    """
    Позволяет суперпользователю просматривать систему от имени другого пользователя.
    В сессии хранится _impersonate_user_id. Оригинальный пользователь доступен
    как request.real_user. Если impersonation не активен, request.real_user == request.user.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.real_user = request.user
        request.is_impersonating = False

        impersonate_id = request.session.get("_impersonate_user_id")
        if impersonate_id and request.user.is_authenticated and request.user.is_superuser:
            try:
                target = User.objects.select_related("profile").get(pk=impersonate_id)
                request.real_user = request.user
                request.user = target
                request.is_impersonating = True
            except User.DoesNotExist:
                del request.session["_impersonate_user_id"]

        return self.get_response(request)

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
        own_orgs = list(Organization.objects.own_for(account))
        request.own_orgs = own_orgs

        if not own_orgs:
            request.current_org = None
            return

        by_id = {o.pk: o for o in own_orgs}
        session_org_id = request.session.get("current_org_id")
        org = by_id.get(session_org_id) if session_org_id else None

        # profile подгружаем только если session-hit промахнулся —
        # на hot path обычного запроса это экономит один SELECT
        # на accounts_userprofile.
        if org is None:
            profile = getattr(request.user, "profile", None)
            last_id = getattr(profile, "last_active_org_id", None)
            if last_id:
                org = by_id.get(last_id)
                if org is None and profile is not None:
                    profile.last_active_org = None
                    profile.save(update_fields=["last_active_org"])

        if org is None:
            org = own_orgs[0]

        if request.session.get("current_org_id") != org.pk:
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
