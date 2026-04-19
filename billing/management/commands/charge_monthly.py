"""
Management-команда месячного биллинга подписок (ТЗ §9).

Запускается cron'ом 2-го числа каждого месяца в 00:30 MSK (настройка
будет добавлена в итерации 6, сейчас команда доступна только ручным
вызовом).

Использование:
    python manage.py charge_monthly                    # полный прогон
    python manage.py charge_monthly --dry-run          # расчёт без списаний
    python manage.py charge_monthly --account-id 42    # один аккаунт
    python manage.py charge_monthly --account-id 42 --dry-run
"""
import logging

from django.core.management.base import BaseCommand, CommandError

from billing.services.charging import charge_monthly


logger = logging.getLogger("billing")


class Command(BaseCommand):
    help = "Ежемесячное списание подписок (Billing v2)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Считать суммы и выводить отчёт, но не изменять БД",
        )
        parser.add_argument(
            "--account-id",
            type=int,
            default=None,
            help="Обработать только один аккаунт (для отладки)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        account_id = options["account_id"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN: списания не будут выполнены"))
        if account_id is not None:
            self.stdout.write(f"Ограничение: account_id={account_id}")

        try:
            report = charge_monthly(dry_run=dry_run, account_id=account_id)
        except RuntimeError as exc:
            # advisory lock busy — другой процесс уже запустил charge_monthly
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            f"charge_monthly: processed={report['processed']} "
            f"charged={report['charged']} past_due={report['past_due']} "
            f"skipped={report['skipped']} errors={len(report['errors'])}"
        )
        for err in report["errors"]:
            self.stdout.write(self.style.ERROR(
                f"  account_id={err['account_id']}: {err['error']}"
            ))
