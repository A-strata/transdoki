import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from transdoki.tenancy import get_request_account

from . import cloudpayments as cp_service
from .cloudpayments import CloudPaymentsError, PaymentOrderNotFound
from .forms import DepositForm
from .constants import (
    DAILY_RATE_ORG,
    DAILY_RATE_USER,
    DAILY_RATE_VEHICLE,
    FREE_TIER_ORGS,
    FREE_TIER_USERS,
    FREE_TIER_VEHICLES,
)
from .models import BillingTransaction

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security")

# Коды ответа CloudPayments:
#   0  — принято, всё хорошо
#   10 — отклонить платёж (повтор не нужен, ошибка на нашей стороне постоянная)
#   20 — временная ошибка (CloudPayments повторит до 100 раз с нарастающим интервалом)
_CP_OK = 0
_CP_REJECT = 10
_CP_RETRY = 20

DAYS_IN_MONTH = 30


class PricingView(View):
    template_name = "pricing.html"

    def get(self, request):
        monthly_org = int(DAILY_RATE_ORG * DAYS_IN_MONTH)
        monthly_vehicle = int(DAILY_RATE_VEHICLE * DAYS_IN_MONTH)
        monthly_user = int(DAILY_RATE_USER * DAYS_IN_MONTH)
        context = {
            "free_orgs": FREE_TIER_ORGS,
            "free_vehicles": FREE_TIER_VEHICLES,
            "free_users": FREE_TIER_USERS,
            "monthly_org": monthly_org,
            "monthly_vehicle": monthly_vehicle,
            "monthly_user": monthly_user,
            "min_paid": min(monthly_org, monthly_vehicle, monthly_user),
        }
        return render(request, self.template_name, context)


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

    # ВРЕМЕННЫЙ DEBUG — логируем все HTTP-заголовки чтобы найти нужный
    hmac_headers = {k: v for k, v in request.META.items() if k.startswith("HTTP_") and ("HMAC" in k or "SIGN" in k or "HASH" in k or "TOKEN" in k)}
    logger.warning("cloudpayments.headers_debug hmac_related=%r", hmac_headers)

    signature = request.META.get("HTTP_X_CONTENT_HMAC", "")
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

    try:
        cp_service.handle_check_webhook(payload)
    except (PaymentOrderNotFound, CloudPaymentsError) as e:
        logger.info("cloudpayments.check_rejected: %s", e)
        return JsonResponse({"code": _CP_REJECT})
    except Exception:
        logger.exception("cloudpayments.check_error payload=%s", payload.get("InvoiceId"))
        return JsonResponse({"code": _CP_RETRY})

    return JsonResponse({"code": _CP_OK})


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

    try:
        cp_service.handle_pay_webhook(payload)
    except PaymentOrderNotFound as e:
        # Неизвестный заказ — повтор не поможет
        logger.warning("cloudpayments.pay_unknown_order: %s", e)
        return JsonResponse({"code": _CP_REJECT})
    except CloudPaymentsError as e:
        logger.warning("cloudpayments.pay_rejected: %s", e)
        return JsonResponse({"code": _CP_REJECT})
    except Exception:
        logger.exception("cloudpayments.pay_error payload=%s", payload.get("InvoiceId"))
        # Временная ошибка — просим CP повторить, деньги уже списаны с карты
        return JsonResponse({"code": _CP_RETRY})

    return JsonResponse({"code": _CP_OK})


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

    try:
        cp_service.handle_fail_webhook(payload)
    except Exception:
        # Не критично: деньги не трогаем, просто логируем
        logger.exception("cloudpayments.fail_error payload=%s", payload.get("InvoiceId"))

    return JsonResponse({"code": _CP_OK})
