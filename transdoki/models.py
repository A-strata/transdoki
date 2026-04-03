from django.conf import settings
from django.db import models


class TenantQuerySet(models.QuerySet):
    def for_account(self, account):
        """Фильтрация по тенанту — основной способ получения данных в views."""
        return self.filter(account=account)


class TenantManager(models.Manager):
    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db)

    def for_account(self, account):
        return self.get_queryset().for_account(account)


class UserOwnedModel(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.PROTECT,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        abstract = True
