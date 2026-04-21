from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _


def validate_unique_trip_number_and_date(
    user, num_of_trip, date_of_trip, instance=None
):
    """
    Валидатор для проверки уникальности
    комбинации номера и даты рейса в рамках account
    """
    # Локальный импорт чтобы избежать циклических зависимостей
    from .models import Trip

    account_id = getattr(getattr(user, "profile", None), "account_id", None)

    # Проверяем что все необходимые данные есть
    if not all([account_id, num_of_trip, date_of_trip]):
        return

    # Базовый запрос для поиска дубликатов в рамках account.
    # all_objects — UniqueConstraint действует и на soft-deleted записи,
    # поэтому дубликат надо ловить и среди удалённых.
    qs = Trip.all_objects.filter(
        account_id=account_id,
        num_of_trip=num_of_trip,
        date_of_trip=date_of_trip,
    )

    # Исключаем текущий instance при редактировании
    if instance and instance.pk:
        qs = qs.exclude(pk=instance.pk)

    if qs.exists():
        raise ValidationError(
            "Рейс с таким номером и датой уже существует. "
            "Пожалуйста, выберите другой номер или дату."
        )


def validate_client_cannot_be_carrier(client, carrier):
    """
    Валидатор для проверки, что заказчик не может быть перевозчиком
    """
    if client and carrier and client == carrier:
        raise ValidationError(
            "Заказчик не может быть одновременно перевозчиком. "
            "Пожалуйста, выберите другую организацию "
            "в качестве перевозчика или заказчика."
        )


def validate_our_company_participation(client, carrier, forwarder=None):
    """
    Валидатор для проверки, что в заявке участвует наша фирма
    в одной из трёх ролей: заказчик, перевозчик или экспедитор.
    """
    our_participation = any(
        [
            client.is_own_company if client else False,
            carrier.is_own_company if carrier else False,
            forwarder.is_own_company if forwarder else False,
        ]
    )

    if not our_participation:
        raise ValidationError(
            "Ваша компания должна быть участником перевозки."
            "Укажите Вашу компанию в качестве заказчика, перевозчика или экспедитора."
        )


def validate_forwarder(forwarder, client, carrier, current_org=None):
    """
    Экспедитор, если задан:
    - должен быть own-фирмой аккаунта (is_own_company=True);
    - не должен совпадать с заказчиком или перевозчиком.

    Исторически здесь было ограничение «forwarder должен совпадать с
    текущей фирмой в навбаре» — оно имело смысл, пока поле было
    статическим (рендерилось как current_org без возможности смены).
    С Phase 1.5 UI (role-driven autocomplete) пользователь может выбрать
    в качестве экспедитора ЛЮБУЮ из своих фирм; ограничение стало
    некорректным и снято. Параметр current_org оставлен для обратной
    совместимости сигнатуры.
    """
    if forwarder is None:
        return

    if not forwarder.is_own_company:
        raise ValidationError(
            {"forwarder": "Экспедитором может быть только ваша фирма."}
        )

    if client and forwarder.pk == client.pk:
        raise ValidationError(
            {"forwarder": "Экспедитор не может совпадать с заказчиком."}
        )

    if carrier and forwarder.pk == carrier.pk:
        raise ValidationError(
            {"forwarder": "Экспедитор не может совпадать с перевозчиком."}
        )


def validate_trailer_for_truck(truck, trailer):
    """
    Валидатор: если автомобиль типа "Тягач седельный", то прицеп обязателен
    """
    if truck and truck.vehicle_type == "truck" and not trailer:
        raise ValidationError(
            {"trailer": "Для указанного автомобиля обязателен прицеп"}
        )


def validate_vehicles_belong_to_carrier(truck, trailer, carrier):
    """
    Валидатор: автомобиль и прицеп (если обязателен)
    должны принадлежать перевозчику
    """
    errors = {}

    # Проверяем автомобиль
    if truck and truck.owner != carrier:
        errors["truck"] = (
            "Автомобиль должен принадлежать перевозчику."
            f"Этот автомбиль принадлежит {truck.owner.short_name}"
        )

    # Проверяем прицеп (если он обязателен для седельного тягача)
    if truck and truck.vehicle_type == "truck" and trailer and trailer.owner != carrier:
        errors["trailer"] = (
            "Прицеп должен принадлежать перевозчику"
            f"Этот прицеп принадлежит {truck.owner.short_name}"
        )

    # Проверяем прицеп (если он указан для одиночного грузовика)
    if (
        truck
        and truck.vehicle_type == "single"
        and trailer
        and trailer.owner != carrier
    ):
        errors["trailer"] = (
            "Прицеп должен принадлежать перевозчику"
            f"Этот прицеп принадлежит {truck.owner.short_name}"
        )

    if errors:
        raise ValidationError(errors)


class RussianMinValueValidator(MinValueValidator):
    message = _("Убедитесь, что значение больше или равно %(limit_value)s.")

    def __init__(self, limit_value, message=None):
        if message is None:
            message = self.message
        super().__init__(limit_value, message)


def _is_filled(value):
    """
    Поле считается заполненным, если там не None и не пустая строка.
    Важно: 0 считается заполненным значением.
    """
    return value is not None and value != ""


def validate_costs_by_our_company_role(
    *, client, carrier, client_cost, carrier_cost, forwarder=None
):
    """
    Правило:
    - Если задан экспедитор — оба поля cost разрешены (маржа посредника).
    - Если наша фирма = перевозчик (carrier.is_own_company=True),
      то можно указывать только client_cost.
      => carrier_cost должен быть пустым.
    - Если наша фирма = заказчик (client.is_own_company=True),
      то можно указывать только carrier_cost.
      => client_cost должен быть пустым.

    Оба поля остаются необязательными.
    """
    # Для экспедитора — ограничений нет, он явно посредник с двумя суммами
    if forwarder is not None:
        return

    errors = {}

    we_are_carrier = bool(carrier and carrier.is_own_company)
    we_are_client = bool(client and client.is_own_company)

    # Новый кейс: обе стороны — наши компании, но это разные юрлица.
    # В этом случае разрешаем заполнять client_cost.
    different_own_companies = bool(
        we_are_carrier
        and we_are_client
        and client
        and carrier
        and client.pk != carrier.pk
    )

    if we_are_carrier and not different_own_companies and _is_filled(carrier_cost):
        errors["carrier_cost"] = (
            "Когда наша фирма выступает перевозчиком, "
            'поле "Стоимость для перевозчика" должно быть пустым.'
        )

    if we_are_client and not different_own_companies and _is_filled(client_cost):
        errors["client_cost"] = (
            "Когда наша фирма выступает заказчиком, "
            'поле "Стоимость для клиента" должно быть пустым.'
        )

    if errors:
        raise ValidationError(errors)
