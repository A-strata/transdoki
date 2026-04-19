"""
Миграция AccountModule: CharField `module` → FK на billing.Module.

На проде максимум одна запись (code='contracts') — безопасно.
Стратегия: снять записи в лог, очистить таблицу, перестроить схему,
восстановить через FK по коду модуля.

Порядок операций учитывает особенности SQLite (unique_together снимается
до удаления полей, FK создаётся nullable → populate → NOT NULL).
"""
import logging

from django.db import migrations, models
import django.db.models.deletion


logger = logging.getLogger(__name__)


def dump_old_modules(apps, schema_editor):
    """Сохранить данные старой таблицы в атрибут функции и очистить таблицу."""
    AccountModule = apps.get_model("billing", "AccountModule")
    rows = list(
        AccountModule.objects.values("id", "account_id", "module", "enabled_at")
    )
    logger.info("accountmodule_rebuild: dump of %d rows: %s", len(rows), rows)
    dump_old_modules._dump = rows
    AccountModule.objects.all().delete()


def restore_modules(apps, schema_editor):
    """Восстановить записи после пересоздания схемы, с FK на Module."""
    AccountModule = apps.get_model("billing", "AccountModule")
    Module = apps.get_model("billing", "Module")

    rows = getattr(dump_old_modules, "_dump", [])
    if not rows:
        return

    modules_by_code = {m.code: m for m in Module.objects.all()}
    for row in rows:
        module = modules_by_code.get(row["module"])
        if not module:
            logger.warning(
                "accountmodule_rebuild: unknown module code=%r, skipping row id=%s",
                row["module"],
                row["id"],
            )
            continue
        AccountModule.objects.create(
            account_id=row["account_id"],
            module=module,
            is_active=True,
        )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0011_userprofile_last_active_org"),
        ("billing", "0005_seed_plans_and_subscriptions"),
    ]

    operations = [
        # 1. Снять unique_together ДО удаления поля module (SQLite иначе падает
        # на "no such column: module" при попытке пересоздать индекс).
        migrations.AlterUniqueTogether(
            name="accountmodule",
            unique_together=set(),
        ),

        # 2. Дамп + очистка таблицы. Делаем до удаления полей, пока доступен old schema.
        migrations.RunPython(dump_old_modules, reverse_code=reverse_noop),

        # 3. Удалить устаревшие поля.
        migrations.RemoveField(model_name="accountmodule", name="enabled_at"),
        migrations.RemoveField(model_name="accountmodule", name="enabled_by"),
        migrations.RemoveField(model_name="accountmodule", name="expires_at"),
        migrations.RemoveField(model_name="accountmodule", name="module"),

        # 4. Добавить новые поля. module — пока nullable, NOT NULL поставим
        # на последнем шаге после restore_modules.
        migrations.AddField(
            model_name="accountmodule",
            name="module",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="activations",
                to="billing.module",
                verbose_name="Модуль",
            ),
        ),
        migrations.AddField(
            model_name="accountmodule",
            name="started_at",
            field=models.DateTimeField(auto_now_add=True, verbose_name="Подключён"),
        ),
        migrations.AddField(
            model_name="accountmodule",
            name="ended_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Отключён"),
        ),
        migrations.AddField(
            model_name="accountmodule",
            name="is_active",
            field=models.BooleanField(db_index=True, default=True, verbose_name="Активен"),
        ),

        # 5. Обновить related_name FK account.
        migrations.AlterField(
            model_name="accountmodule",
            name="account",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="account_modules",
                to="accounts.account",
                verbose_name="Аккаунт",
            ),
        ),

        # 6. Восстановить ранее сохранённые записи (с валидным FK).
        migrations.RunPython(restore_modules, reverse_code=reverse_noop),

        # 7. Зафиксировать NOT NULL на module и добавить UniqueConstraint.
        migrations.AlterField(
            model_name="accountmodule",
            name="module",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="activations",
                to="billing.module",
                verbose_name="Модуль",
            ),
        ),
        migrations.AddConstraint(
            model_name="accountmodule",
            constraint=models.UniqueConstraint(
                fields=("account", "module"),
                name="accountmodule_unique_account_module",
            ),
        ),
    ]
