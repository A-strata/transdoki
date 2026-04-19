"""
Месячный биллинг подписок (ТЗ §6.3).

Главная точка входа — charge_monthly(dry_run=False). Запускается cron'ом
2-го числа каждого месяца в 00:30 MSK. Обрабатывает все подписки, у которых
current_period_end уже наступил.

Архитектурные инварианты:

1. Идемпотентность. UniqueConstraint (account, period_start) на BillingPeriod
   делает повторный запуск за тот же период безопасным: при попытке создать
   дубль ловим IntegrityError и продолжаем. На прикладном уровне — проверка
   existing BillingPeriod через .filter(...).exists() до создания.

2. Атомарность одного аккаунта. _charge_one_subscription выполняет все
   изменения (BillingPeriod, списание с баланса, BillingTransaction,
   обновление Subscription) в одной transaction.atomic(). При падении
   посреди операций — полный rollback, ни одного частичного состояния.

3. Advisory lock. pg_try_advisory_lock на уровне Postgres исключает
   параллельный запуск charge_monthly (например, если cron запустился дважды
   из-за гонки). На SQLite — no-op: в тестах не требуется, а прод один.

4. Bill by created_at month. Рейсы относятся к периоду своего created_at,
   не к моменту 24-часового подтверждения (ТЗ §3.3). get_trip_usage уже
   это реализует — мы просто передаём границы периода.

5. is_billing_exempt — skip. Exempt-аккаунты пропускаются целиком:
   не создаётся BillingPeriod, не списывается с баланса.
"""
import hashlib
import logging
from contextlib import contextmanager
from decimal import Decimal

from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from billing.models import BillingPeriod, BillingTransaction, Subscription
from billing.services.usage import get_trip_usage


logger = logging.getLogger("billing")

# Константа для advisory lock. Положительное 63-битное число, выведенное
# из строки "billing.charge_monthly" — детерминированное, уникальное.
# Postgres требует bigint, помещающийся в 63 бита (знаковый long).
_LOCK_KEY = int(hashlib.sha256(b"billing.charge_monthly").hexdigest()[:15], 16)


@contextmanager
def advisory_lock(name: str):
    """
    Захватывает advisory lock на Postgres. На других БД — no-op.

    На SQLite (тесты) lock не нужен: нет параллельного выполнения.
    На Postgres (прод) — pg_try_advisory_lock неблокирующий; если lock уже
    держит другой процесс — выбрасываем RuntimeError, чтобы cron не плодил
    параллельные запуски.
    """
    vendor = connection.vendor
    if vendor != "postgresql":
        yield
        return

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [_LOCK_KEY])
        acquired = cursor.fetchone()[0]
        if not acquired:
            raise RuntimeError(
                f"charge_monthly: advisory lock {_LOCK_KEY} busy — "
                "параллельный запуск запрещён"
            )
        try:
            yield
        finally:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [_LOCK_KEY])


def _add_months(dt, months: int):
    """
    Прибавляет `months` к datetime, обрабатывая переход декабрь→январь и
    коррекцию дня для коротких месяцев (31 марта + 1 = 30 апреля, а не 1 мая).

    Локальная реализация — python-dateutil не установлен, добавлять ради
    одной функции избыточно.
    """
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    is_leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    days_per_month = [31, 29 if is_leap else 28, 31, 30, 31, 30,
                      31, 31, 30, 31, 30, 31]
    day = min(dt.day, days_per_month[month - 1])
    return dt.replace(year=year, month=month, day=day)


def charge_monthly(dry_run: bool = False, account_id: int | None = None) -> dict:
    """
    Обрабатывает все подписки, у которых current_period_end <= now.

    Args:
        dry_run: если True — ничего не изменяется в БД, только считается.
        account_id: если задан — обрабатывается только один аккаунт.

    Returns:
        {
            'processed': int,    # обработано подписок
            'charged':   int,    # успешно списано
            'past_due':  int,    # перешли в past_due из-за нехватки баланса
            'skipped':   int,    # пропущены (idempotency hit, exempt, другое)
            'errors':    list,   # исключения в пользу одного аккаунта
        }
    """
    report = {"processed": 0, "charged": 0, "past_due": 0, "skipped": 0, "errors": []}
    now = timezone.now()

    with advisory_lock("charge_monthly"):
        qs = (
            Subscription.objects.select_related("plan", "account", "scheduled_plan")
            .filter(
                status__in=[Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE],
                current_period_end__lte=now,
            )
        )
        if account_id is not None:
            qs = qs.filter(account_id=account_id)

        for subscription in qs:
            try:
                result = _charge_one_subscription(subscription, dry_run=dry_run)
                report["processed"] += 1
                if result.get("skipped"):
                    report["skipped"] += 1
                elif result.get("charged"):
                    report["charged"] += 1
                elif result.get("past_due"):
                    report["past_due"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "charge_monthly: failed for account_id=%s",
                    subscription.account_id,
                )
                report["errors"].append(
                    {"account_id": subscription.account_id, "error": str(exc)}
                )

    logger.info(
        "charge_monthly done: processed=%d charged=%d past_due=%d skipped=%d errors=%d",
        report["processed"], report["charged"], report["past_due"],
        report["skipped"], len(report["errors"]),
    )
    return report


def _charge_one_subscription(subscription: Subscription, dry_run: bool = False) -> dict:
    """
    Обрабатывает одну подписку. Вся логика внутри transaction.atomic().
    Идемпотентна: если BillingPeriod за этот period_start уже есть — no-op.
    """
    account = subscription.account

    # Exempt-аккаунты полностью пропускаются (ТЗ §3.8). Для них period тоже
    # не продвигается — «они живут вне биллингового времени». Если в будущем
    # exempt снимется, current_period_end останется старым и ближайший
    # charge_monthly захватит их в normal flow.
    if account.is_billing_exempt:
        logger.info("charge_monthly: skip exempt account_id=%s", account.pk)
        return {"skipped": True}

    period_start = subscription.current_period_start
    period_end = subscription.current_period_end

    # Идемпотентность: период с таким period_start уже закрыт.
    if BillingPeriod.objects.filter(
        account=account, period_start=period_start.date()
    ).exists():
        logger.info(
            "charge_monthly: already processed account_id=%s period_start=%s",
            account.pk, period_start.date(),
        )
        return {"skipped": True}

    # Сбор данных для расчёта.
    usage = get_trip_usage(account, period_start, period_end)
    limit = subscription.effective_trip_limit
    overage_trips = max(0, usage["confirmed"] - limit) if limit is not None else 0
    overage_price = subscription.effective_overage_price or Decimal("0")
    overage_fee = Decimal(overage_trips) * overage_price

    active_modules = list(
        account.account_modules.filter(is_active=True).select_related("module")
    )
    modules_fee = sum(
        (am.module.monthly_price for am in active_modules), Decimal("0")
    )
    modules_snapshot = [
        {"code": am.module.code, "price": str(am.module.monthly_price)}
        for am in active_modules
    ]

    subscription_fee = subscription.effective_monthly_price
    total = subscription_fee + modules_fee + overage_fee

    if dry_run:
        logger.info(
            "[DRY-RUN] account_id=%s plan=%s confirmed=%d overage=%d "
            "subscription=%s modules=%s overage_fee=%s total=%s",
            account.pk, subscription.plan.code, usage["confirmed"], overage_trips,
            subscription_fee, modules_fee, overage_fee, total,
        )
        return {
            "dry_run": True,
            "total": total,
            "subscription_fee": subscription_fee,
            "modules_fee": modules_fee,
            "overage_fee": overage_fee,
            "confirmed_trips": usage["confirmed"],
            "overage_trips": overage_trips,
        }

    # Реальный флоу — всё в одной транзакции.
    with transaction.atomic():
        try:
            billing_period = BillingPeriod.objects.create(
                account=account,
                period_start=period_start.date(),
                period_end=period_end.date(),
                plan_code=subscription.plan.code,
                confirmed_trips=usage["confirmed"],
                trip_limit=limit,
                overage_trips=overage_trips,
                subscription_fee=subscription_fee,
                modules_fee=modules_fee,
                overage_fee=overage_fee,
                total=total,
                modules_snapshot=modules_snapshot,
                status=BillingPeriod.Status.DRAFT,
            )
        except IntegrityError:
            # Параллельный запуск обогнал нас между SELECT-проверкой и INSERT.
            # Это доп. страховка к advisory lock (на случай SQLite или ручного
            # запуска команды).
            logger.warning(
                "charge_monthly: race on BillingPeriod unique constraint, "
                "account_id=%s period_start=%s — skipping",
                account.pk, period_start.date(),
            )
            return {"skipped": True}

        if total == Decimal("0"):
            # Нечего списывать — просто закрываем период как paid
            # и двигаем subscription вперёд.
            billing_period.status = BillingPeriod.Status.PAID
            billing_period.charged_at = timezone.now()
            billing_period.save(update_fields=["status", "charged_at"])
            _apply_scheduled_plan(subscription)
            subscription.status = Subscription.Status.ACTIVE
            subscription.past_due_since = None
            _advance_period(subscription)
            return {"charged": True, "total": total}

        if account.balance >= total:
            # Хватает баланса — списываем.
            _charge_balance(
                account,
                total,
                BillingTransaction.Kind.SUBSCRIPTION,
                billing_period=billing_period,
                description=(
                    f"Подписка {subscription.plan.name}, период "
                    f"{period_start.date()}..{period_end.date()}"
                ),
            )
            billing_period.status = BillingPeriod.Status.PAID
            billing_period.charged_at = timezone.now()
            billing_period.save(update_fields=["status", "charged_at"])

            _apply_scheduled_plan(subscription)
            subscription.status = Subscription.Status.ACTIVE
            subscription.past_due_since = None
            _advance_period(subscription)
            return {"charged": True, "total": total}

        # Нехватка баланса — past_due. BillingPeriod остаётся invoiced,
        # сумма «висит» задолженностью. Баланс не трогаем (клиент пополнит
        # → на следующем запуске charge_monthly повторно? Нет, advance_period
        # мы уже сделали. Логика past_due: подписку двигаем вперёд, но статус
        # past_due держит её в выборке charge_monthly на следующем запуске
        # — и выставленный BillingPeriod обработает отдельная функция в
        # итерации 4 (recover_past_due).
        #
        # Для текущей итерации 3 — просто помечаем invoiced и переводим
        # в past_due. Восстановление баланса — отдельная задача.
        billing_period.status = BillingPeriod.Status.INVOICED
        billing_period.save(update_fields=["status"])

        if subscription.status != Subscription.Status.PAST_DUE:
            subscription.status = Subscription.Status.PAST_DUE
            subscription.past_due_since = timezone.now()
        _advance_period(subscription)
        return {"past_due": True, "total": total}


def _charge_balance(
    account,
    amount: Decimal,
    kind: str,
    billing_period: BillingPeriod | None = None,
    description: str = "",
) -> BillingTransaction:
    """
    Списывает amount с баланса аккаунта и создаёт BillingTransaction.

    Используется ВНУТРИ transaction.atomic() — собственной транзакции
    не открывает, чтобы весь _charge_one_subscription был атомарным.
    select_for_update на Account гарантирует корректность баланса при
    параллельных операциях (deposit от CloudPayments, например).

    amount положительный в записи `BillingTransaction.amount` — направление
    определяется kind. Это соглашение legacy-кода (см. balance.py::withdraw).
    """
    from accounts.models import Account

    acc = Account.objects.select_for_update().get(pk=account.pk)
    acc.balance -= amount
    acc.save(update_fields=["balance", "updated_at"])

    return BillingTransaction.objects.create(
        account=acc,
        kind=kind,
        amount=amount,
        balance_after=acc.balance,
        description=description,
        billing_period=billing_period,
    )


def _advance_period(subscription: Subscription):
    """Сдвигает окно подписки на следующий месяц."""
    subscription.current_period_start = subscription.current_period_end
    subscription.current_period_end = _add_months(subscription.current_period_end, 1)
    subscription.save(
        update_fields=[
            "current_period_start",
            "current_period_end",
            "status",
            "past_due_since",
            "plan",
            "scheduled_plan",
            "updated_at",
        ]
    )


def _apply_scheduled_plan(subscription: Subscription):
    """Применяет отложенный даунгрейд, если он запланирован."""
    if subscription.scheduled_plan_id:
        subscription.plan = subscription.scheduled_plan
        subscription.scheduled_plan = None
