import json
import logging
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import ListView, TemplateView

from transdoki.tenancy import get_request_account

from . import cloudpayments as cp_service
from .cloudpayments import CloudPaymentsError, PaymentOrderNotFound
from .exceptions import InsufficientFunds, PlanChangeError
from .forms import DepositForm
from .models import BillingPeriod, BillingTransaction, Plan
from .services import plan_change as plan_change_service
from .services.limits import get_organization_usage, get_user_usage
from .services.usage import get_trip_usage

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security")

# Коды ответа CloudPayments:
#   0  — принято, всё хорошо
#   10 — отклонить платёж (повтор не нужен, ошибка на нашей стороне постоянная)
#   20 — временная ошибка (CloudPayments повторит до 100 раз с нарастающим интервалом)
_CP_OK = 0
_CP_REJECT = 10
_CP_RETRY = 20



class PricingView(View):
    template_name = "pricing.html"

    def get(self, request):
        return render(request, self.template_name)


class TransactionListView(LoginRequiredMixin, ListView):
    model = BillingTransaction
    template_name = "billing/transaction_list.html"
    context_object_name = "transactions"
    paginate_by = 30

    def get_queryset(self):
        account = get_request_account(self.request)
        return BillingTransaction.objects.filter(account=account).select_related("account")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["account"] = get_request_account(self.request)
        return context


class SubscriptionView(LoginRequiredMixin, TemplateView):
    """
    Страница «Мой тариф» (/billing/subscription/).

    4 блока (ТЗ §7.1):
      1. Текущий тариф: имя, цена, дата следующего списания, scheduled_plan.
      2. Прогресс-бары лимитов: рейсы (confirmed/pending), организации, пользователи.
      3. Баланс + прогноз списания + ссылка на пополнение.
      4. История BillingPeriod за последние 12 месяцев.
    """

    template_name = "billing/subscription.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        account = get_request_account(self.request)
        subscription = getattr(account, "subscription", None)

        ctx["account"] = account
        ctx["subscription"] = subscription

        if subscription is None:
            # Защита на случай сломанного инварианта (нет подписки).
            # В норме сигнал auto_create_free_subscription такого не допустит.
            ctx["error"] = "У аккаунта нет подписки. Обратитесь в поддержку."
            return ctx

        # Блок 2: использование и лимиты
        trip_usage = get_trip_usage(
            account, subscription.current_period_start, subscription.current_period_end,
        )
        org_usage = get_organization_usage(account)
        user_usage = get_user_usage(account)

        ctx["trip_usage"] = trip_usage
        ctx["org_usage"] = org_usage
        ctx["user_usage"] = user_usage

        # Overage-прогноз для UI (confirmed > limit)
        if trip_usage["limit"] is not None and trip_usage["confirmed"] > trip_usage["limit"]:
            overage = trip_usage["confirmed"] - trip_usage["limit"]
            overage_price = subscription.effective_overage_price or Decimal("0")
            ctx["overage_trips"] = overage
            ctx["overage_fee"] = overage * overage_price
        else:
            ctx["overage_trips"] = 0
            ctx["overage_fee"] = Decimal("0")

        # Блок 3: прогноз следующего списания
        forecast = subscription.effective_monthly_price + ctx["overage_fee"]
        # Активные модули
        modules_fee = sum(
            (am.module.monthly_price for am in account.account_modules.filter(
                is_active=True
            ).select_related("module")),
            Decimal("0"),
        )
        forecast += modules_fee
        ctx["forecast_total"] = forecast
        ctx["forecast_modules_fee"] = modules_fee

        # Хватит ли баланса на прогноз; если нет — сколько дней до нехватки
        if forecast > 0 and account.balance < forecast:
            ctx["balance_insufficient"] = True
        else:
            ctx["balance_insufficient"] = False

        # Блок 4: история за 12 месяцев
        cutoff = timezone.now().date() - timedelta(days=365)
        ctx["billing_periods"] = (
            BillingPeriod.objects.filter(account=account, period_start__gte=cutoff)
            .order_by("-period_start")[:12]
        )

        # Список доступных планов для смены тарифа.
        # Текущий план исключаем; неактивные планы — тоже.
        ctx["available_plans"] = (
            Plan.objects.filter(is_active=True)
            .exclude(pk=subscription.plan_id)
            .order_by("display_order")
        )

        # Corporate: контактный email менеджера (для кнопки «Связаться»)
        # Вынесен в константу — меняется реже кода, чем логика.
        ctx["corporate_contact_email"] = "a.astakhin@gmail.com"

        return ctx


@require_POST
def subscription_upgrade(request):
    """
    AJAX: немедленный апгрейд с pro rata.

    При InsufficientFunds возвращает 402 с параметрами для модалки
    «Требуется N ₽, пополнить?».
    """
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "Требуется авторизация"}, status=401)

    account = get_request_account(request)
    plan_code = request.POST.get("plan_code", "").strip()
    if not plan_code:
        return JsonResponse({"ok": False, "error": "plan_code обязателен"}, status=400)

    try:
        result = plan_change_service.upgrade_plan(account, plan_code)
    except InsufficientFunds as exc:
        # Специальный 402 + сумма для модалки «пополнить и вернуться»
        # Сумма не вытаскивается из исключения (строка), поэтому пересчитаем
        # ожидаемую pro rata вручную для UI.
        required = _estimate_upgrade_price(account, plan_code)
        return JsonResponse(
            {
                "ok": False,
                "error": str(exc),
                "required": str(required) if required else None,
                "balance": str(account.balance),
                "plan_code": plan_code,
            },
            status=402,
        )
    except PlanChangeError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except Exception:
        logger.exception("subscription_upgrade.error account_id=%s plan=%s", account.pk, plan_code)
        return JsonResponse({"ok": False, "error": "Внутренняя ошибка"}, status=500)

    return JsonResponse(
        {
            "ok": True,
            "new_plan": result["new_plan"],
            "charged": str(result["charged"]),
        }
    )


def _estimate_upgrade_price(account, plan_code: str) -> Decimal | None:
    """
    Повторяет расчёт pro rata из upgrade_plan, чтобы в 402-ответе сказать
    клиенту точную сумму, которую нужно пополнить.

    Возвращает None, если план не найден или это не апгрейд.
    """
    try:
        new_plan = Plan.objects.get(code=plan_code, is_active=True)
    except Plan.DoesNotExist:
        return None
    sub = account.subscription
    if new_plan.monthly_price <= sub.effective_monthly_price:
        return None
    now = timezone.now()
    total_days = (sub.current_period_end - sub.current_period_start).days
    days_left = (sub.current_period_end - now).days
    if total_days <= 0 or days_left <= 0:
        return Decimal("0")
    diff = new_plan.monthly_price - sub.effective_monthly_price
    return (diff * Decimal(days_left) / Decimal(total_days)).quantize(Decimal("0.01"))


@require_POST
def subscription_schedule_downgrade(request):
    """AJAX: отложенный даунгрейд с warnings."""
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "Требуется авторизация"}, status=401)

    account = get_request_account(request)
    plan_code = request.POST.get("plan_code", "").strip()
    if not plan_code:
        return JsonResponse({"ok": False, "error": "plan_code обязателен"}, status=400)

    try:
        result = plan_change_service.schedule_downgrade(account, plan_code)
    except PlanChangeError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except Exception:
        logger.exception(
            "subscription_schedule_downgrade.error account_id=%s plan=%s",
            account.pk, plan_code,
        )
        return JsonResponse({"ok": False, "error": "Внутренняя ошибка"}, status=500)

    return JsonResponse(
        {
            "ok": True,
            "effective_at": result["effective_at"].isoformat(),
            "warnings": result["warnings"],
            "plan_code": plan_code,
        }
    )


@require_POST
def subscription_cancel_downgrade(request):
    """AJAX: отмена запланированного даунгрейда."""
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "error": "Требуется авторизация"}, status=401)

    account = get_request_account(request)
    result = plan_change_service.cancel_downgrade(account)
    return JsonResponse({"ok": True, **result})


class DepositView(LoginRequiredMixin, View):
    """
    Страница пополнения баланса через CloudPayments.

    GET  — отображает форму с полем суммы.
    POST — создаёт PaymentOrder, возвращает JSON с параметрами для
           JS-виджета CloudPayments. Фронтенд подхватывает ответ и открывает
           виджет без перезагрузки страницы.

    Почему POST возвращает JSON, а не делает redirect:
    Виджет CloudPayments открывается через JS (new cp.CloudPayments().pay(...)).
    Нам нужно передать в него invoiceId, который генерируется на сервере.
    Поэтому: форма → AJAX POST → JSON с params → JS открывает виджет.
    """

    template_name = "billing/deposit.html"

    def get(self, request):
        account = get_request_account(request)
        return render(request, self.template_name, {
            "form": DepositForm(),
            "account": account,
        })

    def post(self, request):
        account = get_request_account(request)
        form = DepositForm(request.POST)

        if not form.is_valid():
            errors = {field: e.get_json_data() for field, e in form.errors.items()}
            return JsonResponse({"ok": False, "errors": errors}, status=400)

        try:
            widget_params = cp_service.create_payment_order(
                account=account,
                amount=form.cleaned_data["amount"],
            )
        except ValueError as e:
            return JsonResponse({"ok": False, "errors": {"amount": [{"message": str(e)}]}}, status=400)
        except Exception:
            logger.exception("deposit.create_order_error account_id=%s", account.pk)
            return JsonResponse(
                {"ok": False, "errors": {"__all__": [{"message": "Внутренняя ошибка. Попробуйте позже."}]}},
                status=500,
            )

        return JsonResponse({"ok": True, "widget_params": widget_params})


# ---------------------------------------------------------------------------
# CloudPayments webhook views
# ---------------------------------------------------------------------------
# Все три endpoint'а регистрируются в личном кабинете CloudPayments после
# регистрации. Сами view не зависят от credentials — только HMAC-проверка
# потребует заполненного CLOUDPAYMENTS_API_SECRET в .env.
# ---------------------------------------------------------------------------


def _verify_and_parse(request) -> tuple[dict | None, JsonResponse | HttpResponseForbidden | None]:
    """
    Проверяет HMAC-подпись и парсит тело запроса от CloudPayments.

    ВАЖНО: request.body нужно прочитать ДО обращения к request.POST.
    Django читает тело запроса лениво и кеширует его — если POST обратиться
    первым, raw bytes для HMAC будут недоступны.

    Возвращает (payload_dict, None) при успехе
    или (None, error_response) при ошибке.
    """
    raw_body = request.body  # читаем первым — нужен для HMAC

    signature = request.META.get("HTTP_CONTENT_HMAC", "")
    if not cp_service.verify_webhook_hmac(raw_body, signature):
        security_logger.warning(
            "cloudpayments.webhook_bad_hmac ip=%s path=%s",
            request.META.get("REMOTE_ADDR"),
            request.path,
        )
        # 403 без тела — CP не будет повторять, запрос явно не от CP
        return None, HttpResponseForbidden()

    content_type = request.content_type or ""
    if "application/json" in content_type:
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            logger.error("cloudpayments.webhook_bad_json path=%s", request.path)
            return None, JsonResponse({"code": _CP_RETRY}, status=400)
    else:
        # Стандартный формат CP: application/x-www-form-urlencoded
        # request.POST уже распарсен Django из того же закешированного тела
        payload = request.POST.dict()

    return payload, None


@csrf_exempt
@require_POST
def cloudpayments_check(request):
    """
    Check-уведомление: CloudPayments спрашивает "можно ли принять этот платёж?"
    Вызывается ДО списания денег с карты.

    Отвечаем {"code": 0} — разрешаем.
    Отвечаем {"code": 10} — отклоняем (деньги не снимаются, пользователь видит ошибку).
    """
    payload, error = _verify_and_parse(request)
    if error:
        return error

    logger.info(
        "cloudpayments.check_webhook_received order_id=%s test_mode=%s payload=%s",
        payload.get("InvoiceId"),
        payload.get("TestMode"),
        payload,
    )

    try:
        cp_service.handle_check_webhook(payload)
    except (PaymentOrderNotFound, CloudPaymentsError) as e:
        logger.info("cloudpayments.check_rejected: %s", e)
        response = JsonResponse({"code": _CP_REJECT})
        logger.info("cloudpayments.check_response order_id=%s body=%s", payload.get("InvoiceId"), response.content.decode())
        return response
    except Exception:
        logger.exception("cloudpayments.check_error payload=%s", payload.get("InvoiceId"))
        response = JsonResponse({"code": _CP_RETRY})
        logger.info("cloudpayments.check_response order_id=%s body=%s", payload.get("InvoiceId"), response.content.decode())
        return response

    response = JsonResponse({"code": _CP_OK})
    logger.info("cloudpayments.check_response order_id=%s body=%s", payload.get("InvoiceId"), response.content.decode())
    return response


@csrf_exempt
@require_POST
def cloudpayments_pay(request):
    """
    Pay-уведомление: деньги списаны с карты, нужно зачислить на баланс.

    {"code": 0}  — зачислено, всё хорошо.
    {"code": 10} — постоянная ошибка (неизвестный заказ), повтор не поможет.
    {"code": 20} — временная ошибка (например, БД недоступна), CP повторит.

    Идемпотентность реализована в handle_pay_webhook: повторный вызов
    для уже оплаченного заказа возвращает {"code": 0} без зачисления.
    """
    payload, error = _verify_and_parse(request)
    if error:
        return error

    logger.info(
        "cloudpayments.pay_webhook_received order_id=%s cp_tx=%s test_mode=%s payload=%s",
        payload.get("InvoiceId"),
        payload.get("TransactionId"),
        payload.get("TestMode"),
        payload,
    )

    try:
        cp_service.handle_pay_webhook(payload)
    except PaymentOrderNotFound as e:
        # Неизвестный заказ — повтор не поможет
        logger.warning("cloudpayments.pay_unknown_order: %s", e)
        response = JsonResponse({"code": _CP_REJECT})
        logger.info("cloudpayments.pay_response order_id=%s body=%s", payload.get("InvoiceId"), response.content.decode())
        return response
    except CloudPaymentsError as e:
        logger.warning("cloudpayments.pay_rejected: %s", e)
        response = JsonResponse({"code": _CP_REJECT})
        logger.info("cloudpayments.pay_response order_id=%s body=%s", payload.get("InvoiceId"), response.content.decode())
        return response
    except Exception:
        logger.exception("cloudpayments.pay_error payload=%s", payload.get("InvoiceId"))
        # Временная ошибка — просим CP повторить, деньги уже списаны с карты
        response = JsonResponse({"code": _CP_RETRY})
        logger.info("cloudpayments.pay_response order_id=%s body=%s", payload.get("InvoiceId"), response.content.decode())
        return response

    response = JsonResponse({"code": _CP_OK})
    logger.info("cloudpayments.pay_response order_id=%s body=%s", payload.get("InvoiceId"), response.content.decode())
    return response


@csrf_exempt
@require_POST
def cloudpayments_fail(request):
    """
    Fail-уведомление: платёж не прошёл, деньги НЕ были списаны.

    Всегда отвечаем {"code": 0} — даже при внутренней ошибке.
    Fail-уведомление информационное: баланс не затронут, повторять нечего.
    """
    payload, error = _verify_and_parse(request)
    if error:
        return error

    logger.info(
        "cloudpayments.fail_webhook_received order_id=%s cp_tx=%s test_mode=%s payload=%s",
        payload.get("InvoiceId"),
        payload.get("TransactionId"),
        payload.get("TestMode"),
        payload,
    )

    try:
        cp_service.handle_fail_webhook(payload)
    except Exception:
        # Не критично: деньги не трогаем, просто логируем
        logger.exception("cloudpayments.fail_error payload=%s", payload.get("InvoiceId"))

    response = JsonResponse({"code": _CP_OK})
    logger.info("cloudpayments.fail_response order_id=%s body=%s", payload.get("InvoiceId"), response.content.decode())
    return response
