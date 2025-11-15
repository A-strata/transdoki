from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

SESSION_TIMEOUT = 2


class UserProfile(models.Model):
    """Профиль пользователя для хранения бизнес-лимитов и настроек"""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name="Пользователь"
    )
    max_sessions = models.PositiveIntegerField(
        default=1,
        verbose_name="Лимит одновременных сессий"
    )
    max_own_companies = models.PositiveIntegerField(
        default=1,
        verbose_name="Лимит собственных компаний"
    )

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"
        db_table = 'accounts_userprofile'

    def __str__(self):
        return f"Профиль {self.user.username}"

    @property
    def own_companies_count(self):
        """Количество компаний, отмеченных как 'Мои'"""
        from organizations.models import Organization
        return Organization.objects.filter(
            created_by=self.user,
            is_own_company=True
        ).count()

    def can_add_own_company(self):
        """Проверяет, можно ли добавить еще одну свою компанию"""
        return self.own_companies_count < self.max_own_companies

    @property
    def active_sessions_count(self):
        """Количество активных сессий (с учетом таймаута 2 часа)"""
        # Импорт здесь чтобы избежать circular import
        from .models import UserSession
        return UserSession.objects.filter(
            user=self.user,
            is_active=True,
            last_activity__gte=timezone.now() - timedelta(
                hours=SESSION_TIMEOUT)
        ).count()

    def can_add_session(self):
        """Проверяет, можно ли создать новую сессию"""
        return self.active_sessions_count < self.max_sessions

    def get_own_companies(self):
        """Возвращает queryset собственных компаний пользователя"""
        from organizations.models import Organization
        return Organization.objects.filter(
            created_by=self.user,
            is_own_company=True
        )


class UserSession(models.Model):
    """Отслеживание активных сессий пользователя"""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions',
        verbose_name="Пользователь"
    )
    session_key = models.CharField(
        max_length=40,
        db_index=True,
        verbose_name="Ключ сессии"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    last_activity = models.DateTimeField(
        auto_now=True,
        verbose_name="Последняя активность"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активна"
    )

    class Meta:
        verbose_name = "Сессия пользователя"
        verbose_name_plural = "Сессии пользователей"
        db_table = 'accounts_usersession'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['last_activity']),
        ]

    def __str__(self):
        return f"Сессия {self.user.username} ({self.session_key})"


# Сигналы для автоматического создания профиля
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Автоматически создает профиль при создании пользователя"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Автоматически сохраняет профиль при сохранении пользователя"""
    if hasattr(instance, 'profile'):
        instance.profile.save()
