"""
Management-команда для ежедневного перевода просроченных past_due в suspended.

Запускается cron'ом раз в день (ТЗ §10). Использует тот же паттерн
advisory lock, что и charge_monthly, чтобы исключить параллельный запуск.
"""
import hashlib
import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from billing.services.lifecycle import process_past_due_accounts


logger = logging.getLogger("billing")

# Отдельный lock-key, независимый от charge_monthly
_LOCK_KEY = int(hashlib.sha256(b"billing.process_past_due").hexdigest()[:15], 16)


class Command(BaseCommand):
    help = "Переводит просроченные past_due-подписки в suspended (grace 14 дней)"

    def handle(self, *args, **options):
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(%s)", [_LOCK_KEY])
                acquired = cursor.fetchone()[0]
                if not acquired:
                    raise CommandError(
                        f"process_past_due: advisory lock {_LOCK_KEY} busy — "
                        "параллельный запуск запрещён"
                    )
                try:
                    report = process_past_due_accounts()
                finally:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", [_LOCK_KEY])
        else:
            # SQLite — lock не нужен, прод один.
            report = process_past_due_accounts()

        self.stdout.write(
            f"process_past_due: processed={report['processed']} "
            f"suspended={report['suspended']}"
        )
