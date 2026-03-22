from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

SESSION_TIMEOUT_HOURS = 2


class Account(models.Model):
    """
    Tenant-аккаунт (платящий клиент).
    На переходном этапе owner допускается NULL, чтобы безопасно выполнить data migration.
    """

    name = models.CharField(max_length=255, verbose_name="Название аккаунта")
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="owned_accounts",
        null=True,  # В фазе Contract можно сделать NOT NULL
        blank=True,
        verbose_name="Владелец аккаунта",
    )
    max_sessions = models.PositiveIntegerField(
        default=1, verbose_name="Лимит одновременных сессий аккаунта"
    )
    max_own_companies = models.PositiveIntegerField(
        default=1, verbose_name="Лимит собственных компаний аккаунта"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлен")

    class Meta:
        verbose_name = "Аккаунт"
        verbose_name_plural = "Аккаунты"
        db_table = "accounts_account"
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["owner", "is_active"]),
        ]

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """Профиль пользователя для tenant-привязки и роли."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        DISPATCHER = "dispatcher", "Dispatcher"
        LOGIST = "logist", "Logist"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="Пользователь",
    )

    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        related_name="profiles",
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Аккаунт",
    )
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.OWNER, verbose_name="Роль"
    )

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"
        db_table = "accounts_userprofile"
        indexes = [
            models.Index(fields=["account", "role"]),
        ]

    def __str__(self):
        return f"Профиль {self.user.username}"

    @property
    def own_companies_count(self):
        """Количество собственных компаний в рамках account."""
        from organizations.models import Organization

        if not self.account_id:
            return 0

        return Organization.objects.filter(
            account_id=self.account_id,
            is_own_company=True,
        ).count()

    def can_add_own_company(self):
        """Проверяет лимит собственных компаний account."""
        if not self.account_id:
            return False
        return self.own_companies_count < self.account.max_own_companies

    @property
    def active_sessions_count(self):
        """Активные сессии текущего пользователя (служебно)."""
        return UserSession.objects.filter(
            user=self.user,
            is_active=True,
            last_activity__gte=timezone.now() - timedelta(hours=SESSION_TIMEOUT_HOURS),
        ).count()

    @property
    def account_active_sessions_count(self):
        """Активные сессии всех пользователей аккаунта."""
        if not self.account_id:
            return self.active_sessions_count

        return UserSession.objects.filter(
            user__profile__account_id=self.account_id,
            is_active=True,
            last_activity__gte=timezone.now() - timedelta(hours=SESSION_TIMEOUT_HOURS),
        ).count()

    def can_add_session(self):
        """
        Проверяет, можно ли создать новую сессию.
        Лимит только на уровне account.
        """
        if not self.account_id:
            return False
        return self.account_active_sessions_count < self.account.max_sessions

    def get_own_companies(self):
        """Возвращает queryset собственных компаний account."""
        from organizations.models import Organization

        if not self.account_id:
            return Organization.objects.none()

        return Organization.objects.filter(
            account_id=self.account_id,
            is_own_company=True,
        )


class UserSession(models.Model):
    """Отслеживание активных сессий пользователя."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sessions",
        verbose_name="Пользователь",
    )
    session_key = models.CharField(
        max_length=40, db_index=True, verbose_name="Ключ сессии"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    last_activity = models.DateTimeField(
        auto_now=True, verbose_name="Последняя активность"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активна")

    class Meta:
        verbose_name = "Сессия пользователя"
        verbose_name_plural = "Сессии пользователей"
        db_table = "accounts_usersession"
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["last_activity"]),
        ]

    def __str__(self):
        return f"Сессия {self.user.username} ({self.session_key})"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Автоматически создает профиль при создании пользователя."""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Сохраняет профиль, если он уже существует."""
    if hasattr(instance, "profile"):
        instance.profile.save()
