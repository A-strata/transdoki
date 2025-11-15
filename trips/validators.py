from django.core.exceptions import ValidationError


def validate_unique_trip_number_and_date(
        user,
        num_of_trip, date_of_trip,
        instance=None):
    """
    Валидатор для проверки
    уникальности комбинации
    номера и даты рейса для пользователя
    """
    # Локальный импорт чтобы избежать циклических зависимостей
    from .models import Trip

    # Проверяем что все необходимые данные есть
    if not all([user, num_of_trip, date_of_trip]):
        return

    # Базовый запрос для поиска дубликатов
    qs = Trip.objects.filter(
        created_by=user,
        num_of_trip=num_of_trip,
        date_of_trip=date_of_trip
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


def validate_our_company_participation(client, consignor, consignee, carrier):
    """
    Валидатор для проверки, что в заявке участвует наша фирма
    """
    our_participation = any([
        client.is_own_company if client else False,
        consignor.is_own_company if consignor else False,
        consignee.is_own_company if consignee else False,
        carrier.is_own_company if carrier else False
    ])

    if not our_participation:
        raise ValidationError(
            "В заявке должна участвовать ваша компания. "
            "Выберите организацию, помеченную как 'Моя компания'."
        )
