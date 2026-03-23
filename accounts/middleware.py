from datetime import timedelta

from django.utils import timezone

# Обновляем last_activity не чаще одного раза в 5 минут,
# чтобы не писать в БД на каждый запрос.
_UPDATE_INTERVAL = timedelta(minutes=5)


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
