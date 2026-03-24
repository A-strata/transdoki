"""
Сервисный слой для интеграции с CloudPayments.

Статус готовности:
  - create_payment_order()   ✓ готово (не требует API-ключей)
  - verify_webhook_hmac()    ✓ готово (не требует API-ключей)
  - handle_pay_webhook()     ✓ готово (не требует API-ключей)
  - handle_fail_webhook()    ✓ готово (не требует API-ключей)

После регистрации в CloudPayments нужно только прописать в .env:
  CLOUDPAYMENTS_PUBLIC_ID=<публичный ключ>
  CLOUDPAYMENTS_API_SECRET=<секрет для HMAC>
"""

import base64
import hashlib
import hmac
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from billing import services as billing_services
from billing.models import PaymentOrder

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security")


# ---------------------------------------------------------------------------
# Исключения
# ---------------------------------------------------------------------------


class CloudPaymentsError(Exception):
    """Базовое исключение интеграции. Сигнал view вернуть код ошибки CP."""


class PaymentOrderNotFound(CloudPaymentsError):
    """Заказ с переданным InvoiceId не найден. Повтор не имеет смысла."""


class PaymentAmountMismatch(CloudPaymentsError):
    """Сумма в webhook'е не совпадает с суммой заказа. Подозрительно."""


# Минимальная сумма пополнения (₽).
# CloudPayments технически принимает от 1 ₽, но слишком маленькие суммы —
# это либо ошибка, либо попытка проверить карту чужими деньгами.
MIN_DEPOSIT_AMOUNT = Decimal("50.00")

# Максимальная сумма одного пополнения (₽).
# Разумное ограничение на случай ошибки ввода (например, лишний ноль).
MAX_DEPOSIT_AMOUNT = Decimal("100000.00")


# ---------------------------------------------------------------------------
# Публичные функции
# ---------------------------------------------------------------------------


def create_payment_order(account, amount: Decimal) -> dict:
    """
    Создаёт PaymentOrder и возвращает параметры для инициализации
    CloudPayments JS-виджета.

    Вызывается из view, когда пользователь нажимает "Пополнить" и отправляет
    форму с суммой. View передаёт эти параметры в JSON-ответе, а JavaScript
    открывает виджет.

    Пример вызова JS-виджета на фронтенде:
        var widget = new cp.CloudPayments();
        widget.pay('charge', {params}, {callbacks});

    Возвращает dict с ключами, которые нужны виджету.
    Выбрасывает ValueError если сумма некорректная.
    """
    amount = _validate_amount(amount)

    order = PaymentOrder.objects.create(
        account=account,
        amount=amount,
    )

    logger.info(
        "cloudpayments.order_created account_id=%s order_id=%s amount=%s",
        account.pk,
        order.order_id,
        amount,
    )

    return {
        # Публичный ID магазина — отображается в виджете.
        # Берётся из .env; пустая строка пока нет регистрации.
        "publicId": getattr(settings, "CLOUDPAYMENTS_PUBLIC_ID", ""),
        # Что показать пользователю в окне оплаты.
        "description": "Пополнение баланса Transdoki",
        # Сумма в рублях (float, так требует виджет).
        "amount": float(amount),
        "currency": "RUB",
        # InvoiceId — наш UUID. CloudPayments вернёт его в webhook'е.
        # По нему мы найдём нужный аккаунт без сессии пользователя.
        "invoiceId": str(order.order_id),
        # accountId — любой идентификатор плательщика для отчётов CP.
        # Используем pk аккаунта, чтобы было удобно сверяться.
        "accountId": str(account.pk),
    }


def verify_webhook_hmac(raw_body: bytes, signature: str) -> bool:
    """
    Проверяет подпись входящего webhook'а от CloudPayments.

    CloudPayments алгоритм (из документации):
      1. Взять тело запроса (bytes, без изменений)
      2. Вычислить HMAC-SHA256(body, api_secret)
      3. Закодировать результат в base64
      4. Сравнить с заголовком X-Content-HMAC

    Если CLOUDPAYMENTS_API_SECRET не задан — всегда возвращает False.
    Это намеренно: нельзя принимать платежи без настроенного секрета.
    """
    api_secret = getattr(settings, "CLOUDPAYMENTS_API_SECRET", "")
    if not api_secret:
        security_logger.error(
            "cloudpayments.hmac_check_skipped: CLOUDPAYMENTS_API_SECRET не задан"
        )
        return False

    expected = base64.b64encode(
        hmac.new(
            api_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    # ВРЕМЕННЫЙ DEBUG — убрать после диагностики
    import tempfile, os
    _dbg = os.path.join(tempfile.gettempdir(), "cp_webhook_debug.bin")
    with open(_dbg, "wb") as _f:
        _f.write(raw_body)
    security_logger.warning(
        "cloudpayments.hmac_debug body_len=%d computed=%r received=%r saved_to=%s",
        len(raw_body), expected, signature, _dbg,
    )

    # Используем compare_digest чтобы избежать timing attack:
    # обычное == возвращает False при первом несовпадающем байте,
    # по времени ответа можно угадать правильный секрет посимвольно.
    result = hmac.compare_digest(expected, signature)
    if not result:
        security_logger.warning(
            "cloudpayments.hmac_mismatch signature=%s", signature[:16]
        )
    return result


def handle_check_webhook(payload: dict) -> None:
    """
    Обрабатывает Check-уведомление от CloudPayments.

    CloudPayments присылает Check сразу после того как пользователь нажимает
    "Оплатить" в виджете — ещё до списания денег с карты. Это последний шанс
    отклонить платёж на нашей стороне.

    Проверяем два условия:
      1. Заказ с таким InvoiceId существует у нас в БД.
      2. Сумма совпадает — защита от подмены параметров на стороне клиента.

    Если всё хорошо — возвращаем None (view ответит {"code": 0}, CP спишет деньги).
    При любой проблеме — бросаем исключение (view ответит ненулевым кодом, платёж отменится).
    """
    order_id = payload.get("InvoiceId")
    amount_str = payload.get("Amount")

    try:
        order = PaymentOrder.objects.get(order_id=order_id)
    except PaymentOrder.DoesNotExist:
        security_logger.warning(
            "cloudpayments.check_unknown_order order_id=%s", order_id
        )
        raise PaymentOrderNotFound(f"Заказ {order_id} не найден")

    if order.status != PaymentOrder.Status.PENDING:
        # Уже оплаченный/отменённый заказ не должен проходить Check повторно.
        raise CloudPaymentsError(
            f"Заказ {order_id} уже в статусе {order.status}"
        )

    # Проверяем сумму — пользователь не должен иметь возможность изменить её
    # на клиентской стороне и получить пополнение на меньшую сумму.
    try:
        cp_amount = Decimal(str(amount_str)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        raise CloudPaymentsError(f"Некорректная сумма в запросе: {amount_str!r}")

    if cp_amount != order.amount:
        security_logger.warning(
            "cloudpayments.check_amount_mismatch order_id=%s expected=%s got=%s",
            order_id,
            order.amount,
            cp_amount,
        )
        raise PaymentAmountMismatch(
            f"Сумма не совпадает: ожидалось {order.amount}, получено {cp_amount}"
        )

    logger.info(
        "cloudpayments.check_ok order_id=%s amount=%s", order_id, order.amount
    )


def handle_pay_webhook(payload: dict) -> None:
    """
    Обрабатывает уведомление CloudPayments об успешной оплате (тип Pay).

    CloudPayments присылает POST с form-данными. View декодирует их в dict
    и вызывает эту функцию.

    Ключевые поля payload (от CloudPayments, с заглавной буквы):
      InvoiceId      — наш order_id (UUID)
      TransactionId  — ID транзакции в системе CP
      Amount         — сумма платежа
      CardFirstSix   — первые 6 цифр карты (для cp_data)
      CardLastFour   — последние 4 цифры карты (для cp_data)

    Идемпотентность: если заказ уже paid — молча игнорируем.
    Это важно, потому что CloudPayments может прислать одно уведомление
    несколько раз, если наш сервер не ответил вовремя.
    """
    order_id = payload.get("InvoiceId")
    cp_transaction_id = payload.get("TransactionId")

    try:
        order = PaymentOrder.objects.select_for_update().get(order_id=order_id)
    except PaymentOrder.DoesNotExist:
        security_logger.error(
            "cloudpayments.pay_webhook_unknown_order order_id=%s cp_tx=%s",
            order_id,
            cp_transaction_id,
        )
        raise PaymentOrderNotFound(f"Заказ {order_id} не найден")

    # Отклоняем тестовые платежи в production.
    # TestMode=1 приходит при проверке уведомлений в ЛК CP или при тестовых картах.
    if payload.get("TestMode") and not settings.DEBUG:
        security_logger.warning(
            "cloudpayments.test_payment_rejected order_id=%s", order_id
        )
        raise CloudPaymentsError("Тестовый платёж отклонён в production")

    # Идемпотентность: уже обработан — ничего не делаем.
    if order.status == PaymentOrder.Status.PAID:
        logger.info(
            "cloudpayments.pay_webhook_duplicate order_id=%s", order_id
        )
        return

    if order.status == PaymentOrder.Status.FAILED:
        # Платёж пришёл на уже отменённый заказ — подозрительно, логируем.
        security_logger.warning(
            "cloudpayments.pay_on_failed_order order_id=%s cp_tx=%s",
            order_id,
            cp_transaction_id,
        )
        raise ValueError(f"Заказ {order_id} уже находится в статусе failed")

    with transaction.atomic():
        # deposit() сам захватит select_for_update на Account, поэтому
        # порядок блокировок: сначала PaymentOrder (выше), потом Account.
        # Менять порядок нельзя — дедлок.
        billing_tx = billing_services.deposit(
            account=order.account,
            amount=order.amount,
            description=f"Пополнение через CloudPayments (заказ {order.order_id})",
            metadata={
                "source": "cloudpayments",
                "order_id": str(order.order_id),
                "cp_transaction_id": cp_transaction_id,
                "card": _extract_card_info(payload),
            },
        )

        order.status = PaymentOrder.Status.PAID
        order.cp_transaction_id = cp_transaction_id
        order.cp_data = _extract_cp_data(payload)
        order.transaction = billing_tx
        order.completed_at = timezone.now()
        order.save(update_fields=[
            "status", "cp_transaction_id", "cp_data", "transaction", "completed_at"
        ])

    logger.info(
        "cloudpayments.pay_webhook_ok order_id=%s account_id=%s amount=%s",
        order_id,
        order.account_id,
        order.amount,
    )


def handle_fail_webhook(payload: dict) -> None:
    """
    Обрабатывает уведомление CloudPayments об ошибке оплаты (тип Fail).

    Не списывает и не зачисляет ничего — только переводит заказ в статус
    failed и сохраняет данные об ошибке для анализа.

    Поле ReasonCode содержит код отказа банка (например, 5051 — недостаточно
    средств, 5057 — карта заблокирована). Список кодов — в документации CP.
    """
    order_id = payload.get("InvoiceId")

    try:
        order = PaymentOrder.objects.get(order_id=order_id)
    except PaymentOrder.DoesNotExist:
        logger.error(
            "cloudpayments.fail_webhook_unknown_order order_id=%s", order_id
        )
        return  # Fail-webhook не критичен — не бросаем исключение

    if order.status != PaymentOrder.Status.PENDING:
        logger.info(
            "cloudpayments.fail_webhook_not_pending order_id=%s status=%s",
            order_id,
            order.status,
        )
        return

    order.status = PaymentOrder.Status.FAILED
    order.cp_transaction_id = payload.get("TransactionId")
    order.cp_data = _extract_cp_data(payload)
    order.completed_at = timezone.now()
    order.save(update_fields=[
        "status", "cp_transaction_id", "cp_data", "completed_at"
    ])

    logger.info(
        "cloudpayments.fail_webhook_ok order_id=%s reason=%s",
        order_id,
        payload.get("ReasonCode"),
    )


# ---------------------------------------------------------------------------
# Вспомогательные функции (приватные)
# ---------------------------------------------------------------------------


def _validate_amount(amount: Decimal) -> Decimal:
    """
    Проверяет что сумма — корректное положительное число в допустимом диапазоне.
    Выбрасывает ValueError с русскоязычным сообщением (для отображения юзеру).
    """
    try:
        amount = Decimal(str(amount)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        raise ValueError("Некорректная сумма пополнения.")

    if amount < MIN_DEPOSIT_AMOUNT:
        raise ValueError(f"Минимальная сумма пополнения — {MIN_DEPOSIT_AMOUNT} ₽.")

    if amount > MAX_DEPOSIT_AMOUNT:
        raise ValueError(f"Максимальная сумма пополнения — {MAX_DEPOSIT_AMOUNT} ₽.")

    return amount


def _extract_card_info(payload: dict) -> dict:
    """
    Выбирает из payload только данные карты для хранения в metadata.
    Полный номер карты CloudPayments никогда не передаёт — только маску.
    """
    return {
        "first_six": payload.get("CardFirstSix", ""),
        "last_four": payload.get("CardLastFour", ""),
        "exp_date": payload.get("CardExpDate", ""),
        "card_type": payload.get("CardType", ""),
    }


def _extract_cp_data(payload: dict) -> dict:
    """
    Сохраняет все поля из webhook-payload в cp_data для аудита.
    Исключаем только поля, которых в CloudPayments webhook'е нет по умолчанию.
    """
    # Список полей из документации CloudPayments
    # https://developers.cloudpayments.ru/#uvedomleniya
    fields = [
        "TransactionId", "Amount", "Currency", "InvoiceId", "AccountId",
        "SubscriptionId", "Name", "Email", "DateTime", "IpAddress",
        "IpCountry", "IpCity", "IpRegion", "IpDistrict", "IpLatitude",
        "IpLongitude", "CardFirstSix", "CardLastFour", "CardExpDate",
        "CardType", "CardTypeCode", "Issuer", "IssuerBankCountry",
        "Description", "AuthCode", "Data", "Is3DSChecked",
        "Status", "OperationType", "GatewayName", "TestMode",
        "Reason", "ReasonCode",
    ]
    return {k: payload[k] for k in fields if k in payload}
