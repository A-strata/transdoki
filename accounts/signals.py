import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from billing.constants import MAX_SESSIONS_PER_USER

logger = logging.getLogger("security")


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    """
    При каждом входе создаёт UserSession.
    Если активных сессий больше MAX_SESSIONS_PER_USER — логирует подозрительную активность.
    Вход НЕ блокируется (осознанное решение для лучшего UX).
    """
    from accounts.models import UserSession

    session_key = request.session.session_key
    if not session_key:
        return

    UserSession.objects.get_or_create(
        user=user,
        session_key=session_key,
    )

    active_count = UserSession.objects.filter(user=user, is_active=True).count()

    if active_count > MAX_SESSIONS_PER_USER:
        logger.warning(
            "suspicious_activity: multiple_sessions user_id=%s username=%s "
            "active_sessions=%s limit=%s ip=%s",
            user.pk,
            user.username,
            active_count,
            MAX_SESSIONS_PER_USER,
            _get_client_ip(request),
        )


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    """При выходе деактивирует текущую сессию."""
    from accounts.models import UserSession

    if user is None or not request.session.session_key:
        return

    UserSession.objects.filter(
        user=user,
        session_key=request.session.session_key,
    ).update(is_active=False)


def _get_client_ip(request) -> str:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")
