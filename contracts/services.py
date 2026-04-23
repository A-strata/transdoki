import functools
from io import BytesIO
from pathlib import Path

from django.core.files.storage import default_storage
from django.db import transaction
from django.http import FileResponse
from docxtpl import DocxTemplate
from jinja2.sandbox import SandboxedEnvironment

from transdoki.branding import branding_context

from .models import ContractTemplate
from .templates_registry import TEMPLATES


class DocGenerationError(Exception):
    pass


class TemplateNotConfiguredError(DocGenerationError):
    """У аккаунта нет пользовательского шаблона и дефолтный тоже отсутствует."""


# ---------------------------------------------------------------------------
# Сумма прописью (рубли, копейки) — минимальная реализация без зависимостей
# ---------------------------------------------------------------------------

_ONES_F = [
    "",
    "одна",
    "две",
    "три",
    "четыре",
    "пять",
    "шесть",
    "семь",
    "восемь",
    "девять",
]
_ONES_M = [
    "",
    "один",
    "два",
    "три",
    "четыре",
    "пять",
    "шесть",
    "семь",
    "восемь",
    "девять",
]
_TEENS = [
    "десять",
    "одиннадцать",
    "двенадцать",
    "тринадцать",
    "четырнадцать",
    "пятнадцать",
    "шестнадцать",
    "семнадцать",
    "восемнадцать",
    "девятнадцать",
]
_TENS = [
    "",
    "",
    "двадцать",
    "тридцать",
    "сорок",
    "пятьдесят",
    "шестьдесят",
    "семьдесят",
    "восемьдесят",
    "девяносто",
]
_HUNDREDS = [
    "",
    "сто",
    "двести",
    "триста",
    "четыреста",
    "пятьсот",
    "шестьсот",
    "семьсот",
    "восемьсот",
    "девятьсот",
]
_ORDERS = [
    # (singular, 2-4, 5-20, feminine)
    ("", "", "", False),
    ("тысяча", "тысячи", "тысяч", True),
    ("миллион", "миллиона", "миллионов", False),
    ("миллиард", "миллиарда", "миллиардов", False),
]


def _plural(n, one, two, five):
    n = abs(n) % 100
    if 11 <= n <= 19:
        return five
    n = n % 10
    if n == 1:
        return one
    if 2 <= n <= 4:
        return two
    return five


def _triplet(n, feminine=False):
    """Число 0..999 прописью."""
    if n == 0:
        return ""
    parts = []
    h = n // 100
    t = (n % 100) // 10
    o = n % 10
    if h:
        parts.append(_HUNDREDS[h])
    if t == 1:
        parts.append(_TEENS[o])
        return " ".join(parts)
    if t:
        parts.append(_TENS[t])
    if o:
        ones = _ONES_F if feminine else _ONES_M
        parts.append(ones[o])
    return " ".join(parts)


def amount_to_words(amount):
    """Сумма прописью: '1 234.56' → 'Одна тысяча двести тридцать четыре рубля 56 копеек'."""
    from decimal import ROUND_HALF_UP, Decimal

    if amount is None:
        return "—"

    amount = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rubles = int(abs(amount))
    kopecks = int(round((abs(amount) - rubles) * 100))

    if rubles == 0:
        words = "ноль"
    else:
        groups = []
        temp = rubles
        while temp > 0:
            groups.append(temp % 1000)
            temp //= 1000

        parts = []
        for i in range(len(groups) - 1, -1, -1):
            g = groups[i]
            if g == 0:
                continue
            feminine = _ORDERS[i][3] if i < len(_ORDERS) else False
            text = _triplet(g, feminine)
            if i > 0 and i < len(_ORDERS):
                order_word = _plural(g, _ORDERS[i][0], _ORDERS[i][1], _ORDERS[i][2])
                text += " " + order_word
            parts.append(text)
        words = " ".join(parts)

    rub_word = _plural(rubles, "рубль", "рубля", "рублей")
    kop_word = _plural(kopecks, "копейка", "копейки", "копеек")

    result = f"{words} {rub_word} {kopecks:02d} {kop_word}"
    if amount < 0:
        result = "минус " + result
    return result[0].upper() + result[1:]


# ---------------------------------------------------------------------------
# Контекст-билдеры
# ---------------------------------------------------------------------------


_ORG_KEYS = (
    "full_name", "short_name", "inn", "kpp", "ogrn", "address",
    "phone", "email",
    "director_title", "director_name",
    "director_title_genitive", "director_name_genitive",
    "bank_name", "bic", "corr_account", "account_num",
)


@functools.lru_cache(maxsize=1)
def _get_morph():
    """Синглтон MorphAnalyzer. Инициализация тяжёлая (загрузка словарей ~десятки МБ),
    поэтому делаем один раз на процесс."""
    import pymorphy3

    return pymorphy3.MorphAnalyzer()


def _to_genitive(phrase):
    """Склоняет фразу в родительный падеж через pymorphy3."""
    morph = _get_morph()
    words = phrase.split()
    result = []
    for word in words:
        parsed = morph.parse(word)
        best = parsed[0]
        inflected = best.inflect({"gent"})
        result.append(inflected.word if inflected else word)
    # Восстановить регистр по оригиналу
    out = []
    for orig, gen in zip(words, result, strict=True):
        if orig[0].isupper():
            gen = gen[0].upper() + gen[1:]
        out.append(gen)
    return " ".join(out)


def _org_context(org, prefix):
    """Реквизиты организации → словарь с указанным префиксом."""
    if not org:
        return {f"{prefix}_{k}": "—" for k in _ORG_KEYS}

    bank = org.bank_accounts.select_related("account_bank").first()
    return {
        f"{prefix}_full_name": org.full_name or "—",
        f"{prefix}_short_name": org.short_name or "—",
        f"{prefix}_inn": org.inn or "—",
        f"{prefix}_kpp": org.kpp or "—",
        f"{prefix}_ogrn": org.ogrn or "—",
        f"{prefix}_address": org.address or "—",
        f"{prefix}_phone": org.phone or "—",
        f"{prefix}_email": org.email or "—",
        f"{prefix}_director_title": org.director_title or "—",
        f"{prefix}_director_name": org.director_name or "—",
        f"{prefix}_director_title_genitive": (
            _to_genitive(org.director_title) if org.director_title else "—"
        ),
        f"{prefix}_director_name_genitive": (
            _to_genitive(org.director_name) if org.director_name else "—"
        ),
        f"{prefix}_bank_name": bank.account_bank.bank_name if bank else "—",
        f"{prefix}_bic": bank.account_bank.bic if bank else "—",
        f"{prefix}_corr_account": bank.account_bank.corr_account if bank else "—",
        f"{prefix}_account_num": bank.account_num if bank else "—",
    }


def _fmt_date(d):
    return d.strftime("%d.%m.%Y") if d else "—"


def build_contract_context(contract):
    """Плейсхолдеры для шаблона договора."""
    ctx = {
        **branding_context(contract.account),
        "contract_number": contract.number,
        "contract_date": _fmt_date(contract.date_signed),
        "contract_type": contract.get_contract_type_display(),
        "amount": str(contract.amount) if contract.amount is not None else "—",
        "amount_words": amount_to_words(contract.amount),
        "valid_until": _fmt_date(contract.valid_until),
        "subject": contract.subject or "—",
    }
    ctx.update(_org_context(contract.own_company, "own_company"))
    ctx.update(_org_context(contract.contractor, "contractor"))
    return ctx


def build_attachment_context(attachment):
    """Плейсхолдеры для шаблона приложения к договору."""
    ctx = build_contract_context(attachment.contract)
    ctx.update(
        {
            "attachment_number": attachment.number,
            "attachment_date": _fmt_date(attachment.date_signed),
            "attachment_type_display": attachment.get_attachment_type_display(),
            "attachment_amount": (
                str(attachment.amount) if attachment.amount is not None else "—"
            ),
            "attachment_amount_words": amount_to_words(attachment.amount),
            "attachment_subject": attachment.subject or "—",
        }
    )
    return ctx


# ---------------------------------------------------------------------------
# Генерация документа
# ---------------------------------------------------------------------------


def get_default_template_path(template_type):
    """Путь к эталонному DOCX-шаблону из поставки (может не существовать на диске)."""
    return (
        Path(__file__).resolve().parent / "default_templates" / f"{template_type}.docx"
    )


def get_template_for_account(account, template_type):
    """Возвращает путь к файлу шаблона: пользовательский или дефолтный.

    Поднимает TemplateNotConfiguredError, если нет ни того, ни другого —
    это отдельный подкласс DocGenerationError, чтобы view мог отличить
    "пользователь не загрузил шаблон, и в поставке его нет" от прочих ошибок.
    """
    try:
        ct = ContractTemplate.objects.get(
            account=account,
            template_type=template_type,
        )
        if ct.file and Path(ct.file.path).exists():
            return ct.file.path
    except ContractTemplate.DoesNotExist:
        pass

    default = get_default_template_path(template_type)
    if default.exists():
        return str(default)

    raise TemplateNotConfiguredError(
        f"Шаблон «{template_type}» не настроен: ни пользовательский, "
        f"ни дефолтный ({default}) не найдены."
    )


def generate_document(template_path, context):
    """Заполняет DOCX-шаблон контекстом, возвращает BytesIO.

    Рендер идёт через SandboxedEnvironment Jinja2 — это критично для мультитенанта:
    пользовательский шаблон не должен иметь доступ к os/subprocess/etc. через
    выражения вида {{ cycler.__init__.__globals__ }}.
    """
    try:
        doc = DocxTemplate(str(template_path))
        doc.render(context, jinja_env=SandboxedEnvironment())
    except Exception as exc:
        raise DocGenerationError(
            f"Ошибка рендера шаблона {template_path}: {exc}"
        ) from exc

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def generate_contract_response(contract):
    """Генерирует FileResponse для скачивания договора."""
    template_path = get_template_for_account(
        contract.account, contract.contract_type,
    )
    context = build_contract_context(contract)
    buf = generate_document(template_path, context)
    type_display = contract.get_contract_type_display()
    filename = f"{type_display} №{contract.number} от {_fmt_date(contract.date_signed)}.docx"
    return FileResponse(
        buf,
        as_attachment=True,
        filename=filename,
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )


def generate_attachment_response(attachment):
    """Генерирует FileResponse для скачивания приложения к договору."""
    template_path = get_template_for_account(
        attachment.contract.account,
        attachment.attachment_type,
    )
    context = build_attachment_context(attachment)
    buf = generate_document(template_path, context)
    type_display = attachment.get_attachment_type_display()
    filename = (
        f"{type_display} №{attachment.number}"
        f" от {_fmt_date(attachment.date_signed)}.docx"
    )
    return FileResponse(
        buf,
        as_attachment=True,
        filename=filename,
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )


def _schedule_storage_delete(name: str) -> None:
    """После успешного коммита транзакции — удалить файл из storage.

    При откате транзакции файл остаётся на диске (это приемлемый
    сирота-файл; в худшем случае периодический cleanup его подберёт).
    """
    if not name:
        return

    def _do_delete():
        try:
            if default_storage.exists(name):
                default_storage.delete(name)
        except Exception:
            # Не валим пользовательский запрос из-за проблем с FS —
            # оркестрация файлов не должна мешать бизнес-операции.
            pass

    transaction.on_commit(_do_delete)


def replace_template(account, template_type, new_file, user=None):
    """Сохраняет новый шаблон, удаляет старый файл после успешного коммита.

    Атомарно: запись в БД и регистрация post-commit хука идут в одной
    транзакции. Если save() упадёт — БД откатится, старый файл не тронут.
    """
    with transaction.atomic():
        ct, created = ContractTemplate.objects.get_or_create(
            account=account,
            template_type=template_type,
            defaults={"file": new_file, "uploaded_by": user},
        )
        if not created:
            old_name = ct.file.name if ct.file else ""
            ct.file = new_file
            ct.uploaded_by = user
            ct.save(update_fields=["file", "uploaded_by", "uploaded_at"])
            new_name = ct.file.name
            # upload_to детерминированный: storage избегает коллизии, автоматически
            # добавляя суффикс. Если путь отличается — удаляем старый после коммита.
            if old_name and old_name != new_name:
                _schedule_storage_delete(old_name)
    return ct


def delete_template(account, template_type):
    """Удаляет пользовательский шаблон, возвращая к дефолтному.

    Атомарно: сначала DB-запись (в транзакции), затем физический файл
    удаляется только после успешного коммита.
    """
    with transaction.atomic():
        try:
            ct = ContractTemplate.objects.get(
                account=account,
                template_type=template_type,
            )
        except ContractTemplate.DoesNotExist:
            return
        file_name = ct.file.name if ct.file else ""
        ct.delete()
        _schedule_storage_delete(file_name)


# ---------------------------------------------------------------------------
# Реестр плейсхолдеров (для отображения на странице настройки шаблонов)
# ---------------------------------------------------------------------------

_CONTRACT_PLACEHOLDERS = [
    ("contract_number", "Номер договора"),
    ("contract_date", "Дата подписания"),
    ("contract_type", "Тип договора"),
    ("amount", "Сумма"),
    ("amount_words", "Сумма прописью"),
    ("valid_until", "Действует до"),
    ("subject", "Предмет договора"),
    ("own_company_full_name", "Наша компания — полное наименование"),
    ("own_company_short_name", "Наша компания — краткое наименование"),
    ("own_company_inn", "Наша компания — ИНН"),
    ("own_company_kpp", "Наша компания — КПП"),
    ("own_company_ogrn", "Наша компания — ОГРН"),
    ("own_company_address", "Наша компания — адрес"),
    ("own_company_phone", "Наша компания — телефон"),
    ("own_company_email", "Наша компания — email"),
    ("own_company_director_title", "Наша компания — должность руководителя"),
    ("own_company_director_name", "Наша компания — ФИО руководителя"),
    ("own_company_director_title_genitive", "Наша компания — должность (род. падеж)"),
    ("own_company_director_name_genitive", "Наша компания — ФИО (род. падеж)"),
    ("own_company_bank_name", "Наша компания — банк"),
    ("own_company_bic", "Наша компания — БИК"),
    ("own_company_corr_account", "Наша компания — корр. счёт"),
    ("own_company_account_num", "Наша компания — расчётный счёт"),
    ("contractor_full_name", "Контрагент — полное наименование"),
    ("contractor_short_name", "Контрагент — краткое наименование"),
    ("contractor_inn", "Контрагент — ИНН"),
    ("contractor_kpp", "Контрагент — КПП"),
    ("contractor_ogrn", "Контрагент — ОГРН"),
    ("contractor_address", "Контрагент — адрес"),
    ("contractor_phone", "Контрагент — телефон"),
    ("contractor_email", "Контрагент — email"),
    ("contractor_director_title", "Контрагент — должность руководителя"),
    ("contractor_director_name", "Контрагент — ФИО руководителя"),
    ("contractor_director_title_genitive", "Контрагент — должность (род. падеж)"),
    ("contractor_director_name_genitive", "Контрагент — ФИО (род. падеж)"),
    ("contractor_bank_name", "Контрагент — банк"),
    ("contractor_bic", "Контрагент — БИК"),
    ("contractor_corr_account", "Контрагент — корр. счёт"),
    ("contractor_account_num", "Контрагент — расчётный счёт"),
]

_ATTACHMENT_EXTRA = [
    ("attachment_number", "Номер приложения"),
    ("attachment_date", "Дата приложения"),
    ("attachment_type_display", "Тип приложения"),
    ("attachment_amount", "Сумма приложения"),
    ("attachment_amount_words", "Сумма приложения прописью"),
    ("attachment_subject", "Предмет приложения"),
]

PLACEHOLDERS = {
    t.code: (
        _CONTRACT_PLACEHOLDERS + _ATTACHMENT_EXTRA
        if t.is_attachment
        else _CONTRACT_PLACEHOLDERS
    )
    for t in TEMPLATES
}
