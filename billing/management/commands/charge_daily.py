import logging
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from billing import services as billing_services
from billing.models import BillingTransaction

logger = logging.getLogger("django")
security_logger = logging.getLogger("security")


class Command(BaseCommand):
    help = "Ежесуточное списание средств со всех тарифицируемых аккаунтов"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Рассчитать стоимость без фактического списания",
        )

    def handle(self, *args, **options):
        from accounts.models import Account

        dry_run = options["dry_run"]
        today = date.today()

        if dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN — списаний не будет ==="))

        # Все активные аккаунты, кроме освобождённых от биллинга.
        # prefetch_related("profiles") нужен для get_daily_cost → account.profiles.count()
        accounts = (
            Account.objects.filter(is_active=True, is_billing_exempt=False)
            .prefetch_related("profiles")
        )

        total_accounts = 0
        total_charged = 0
        total_skipped = 0
        errors = 0

        for account in accounts:
            try:
                cost, breakdown = billing_services.get_daily_cost(account)

                if cost == 0:
                    total_skipped += 1
                    continue

                total_accounts += 1

                if dry_run:
                    self.stdout.write(
                        f"  [{account.pk}] {account.name}: -{cost} руб. "
                        f"(орг: {breakdown['orgs']['billable']}, "
                        f"машин: {breakdown['vehicles']['billable']}, "
                        f"польз: {breakdown['users']['billable']})"
                    )
                    continue

                billing_services.withdraw(
                    account=account,
                    amount=cost,
                    description=f"Ежесуточное списание {today.isoformat()}",
                    metadata={
                        "date": today.isoformat(),
                        "breakdown": breakdown,
                    },
                )
                total_charged += cost

                logger.info(
                    "charge_daily: account_id=%s charged=%s balance_after=%s",
                    account.pk,
                    cost,
                    account.balance - cost,  # приближённо — точный баланс в withdraw
                )

            except Exception as exc:
                errors += 1
                security_logger.error(
                    "charge_daily: failed account_id=%s error=%s",
                    account.pk,
                    exc,
                )
                self.stderr.write(
                    self.style.ERROR(f"  Ошибка аккаунта [{account.pk}] {account.name}: {exc}")
                )

        # Итог
        if not dry_run:
            summary = (
                f"charge_daily complete: "
                f"charged={total_accounts} accounts / {total_charged} руб., "
                f"skipped={total_skipped} (zero cost), "
                f"errors={errors}"
            )
            logger.info(summary)

            if errors:
                security_logger.warning("charge_daily finished with %s errors", errors)
                self.stdout.write(self.style.WARNING(summary))
            else:
                self.stdout.write(self.style.SUCCESS(summary))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN complete: {total_accounts} аккаунтов к списанию, "
                    f"{total_skipped} с нулевой стоимостью"
                )
            )
