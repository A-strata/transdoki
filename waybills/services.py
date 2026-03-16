from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Vehicle, Waybill, WaybillEvent


ALLOWED_TRANSITIONS = {
    None: {WaybillEvent.Type.OUT, WaybillEvent.Type.TAKE},
    WaybillEvent.Type.OUT: {WaybillEvent.Type.GIVE, WaybillEvent.Type.RETURN},
    WaybillEvent.Type.TAKE: {WaybillEvent.Type.GIVE, WaybillEvent.Type.RETURN},
    WaybillEvent.Type.GIVE: set(),
    WaybillEvent.Type.RETURN: set(),
}


@transaction.atomic
def create_waybill_event(*, waybill_id: int, event_type: str, odometer: int, timestamp=None):
    timestamp = timestamp or timezone.now()

    waybill = (
        Waybill.objects
        .select_for_update()
        .select_related("vehicle", "driver")
        .get(pk=waybill_id)
    )

    vehicle = (
        Vehicle.objects
        .select_for_update()
        .get(pk=waybill.vehicle_id)
    )

    if waybill.status == Waybill.Status.CLOSED:
        raise ValidationError("Путевой лист уже закрыт")

    if not waybill.med_exam_dt:
        raise ValidationError("Нельзя открыть работу без отметки медосмотра")

    if not waybill.tech_exam_dt:
        raise ValidationError("Нельзя открыть работу без отметки техконтроля")

    last_waybill_event = waybill.events.order_by("timestamp", "id").last()
    last_event_type = last_waybill_event.event_type if last_waybill_event else None

    allowed = ALLOWED_TRANSITIONS.get(last_event_type, set())
    if event_type not in allowed:
        raise ValidationError(
            f"Недопустимый переход: после {last_event_type or 'начала'} нельзя выполнить {event_type}"
        )

    # Последнее событие по машине
    last_vehicle_event = (
        WaybillEvent.objects
        .select_for_update()
        .filter(waybill__vehicle=vehicle)
        .order_by("timestamp", "id")
        .last()
    )

    # Контроль пробега
    if last_vehicle_event and odometer < last_vehicle_event.odometer:
        raise ValidationError(
            f"Пробег не может уменьшаться. Последний зафиксированный: {last_vehicle_event.odometer}"
        )

    # Контроль статуса машины
    if event_type in (WaybillEvent.Type.OUT, WaybillEvent.Type.TAKE):
        if vehicle.status == Vehicle.Status.ON_LINE:
            raise ValidationError("Машина уже находится на линии")
    elif event_type in (WaybillEvent.Type.GIVE, WaybillEvent.Type.RETURN):
        if vehicle.status == Vehicle.Status.AT_PARK and event_type == WaybillEvent.Type.RETURN:
            raise ValidationError("Машина уже в парке")

    delta = 0
    if last_vehicle_event:
        delta = odometer - last_vehicle_event.odometer

    event = WaybillEvent.objects.create(
        waybill=waybill,
        event_type=event_type,
        timestamp=timestamp,
        odometer=odometer,
        odometer_delta=delta,
    )

    # Обновление состояния машины
    vehicle.current_odometer = odometer

    if event_type == WaybillEvent.Type.OUT:
        vehicle.status = Vehicle.Status.ON_LINE
    elif event_type == WaybillEvent.Type.TAKE:
        vehicle.status = Vehicle.Status.ON_LINE
    elif event_type == WaybillEvent.Type.GIVE:
        vehicle.status = Vehicle.Status.TRANSFER
    elif event_type == WaybillEvent.Type.RETURN:
        vehicle.status = Vehicle.Status.AT_PARK

    vehicle.save(update_fields=["current_odometer", "status", "updated_at"])

    # Автозакрытие ПЛ
    if event_type in (WaybillEvent.Type.GIVE, WaybillEvent.Type.RETURN):
        waybill.status = Waybill.Status.CLOSED
        waybill.closed_at = timestamp
        waybill.save(update_fields=["status", "closed_at"])

    return event

































# -----------------------------------------------------------------

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils.timezone import localdate

from .models import Waybill


def create_waybill(
        *,
        user,
        organization,
        driver,
        truck,
        trailer=None,
        date=None):
    """
    Создаёт путевой лист с автоматическим номером в пределах года.

    Нумерация ведётся отдельно для каждого пользователя
    и начинается заново с нового года.
    """
    # Создавать путевые листы может только авторизованный пользователь.
    if user is None or not user.is_authenticated:
        raise PermissionDenied('Необходима авторизация.')

    # Если дата не передана, берём текущую локальную дату.
    date = date or localdate()
    year = date.year

    # Финальная защита по организации.
    if (organization.created_by_id != user.id or
            not organization.is_own_company):
        raise ValidationError({
            'organization': ('Можно выбрать только свою организацию'
                             ' с признаком "собственная компания".')
        })

    # Финальная защита по транспорту.
    if truck.created_by_id != user.id:
        raise ValidationError({
            'truck': 'Можно выбрать только свой автомобиль.'
        })

    # Простая доменная защита до сохранения.
    if trailer and truck.pk == trailer.pk:
        raise ValidationError({
            'trailer': 'Автомобиль и прицеп не могут совпадать.'
        })

    # Несколько попыток нужны на случай параллельного создания.
    for attempt in range(5):
        try:
            with transaction.atomic():
                # Ищем последний номер пользователя в пределах года.
                last_number = (
                    Waybill.objects
                    .select_for_update()
                    .filter(
                        created_by=user,
                        year=year,
                    )
                    .aggregate(max_number=Max('number'))['max_number'] or 0
                )

                # Создаём новый путевой лист со следующим номером.
                waybill = Waybill(
                    created_by=user,
                    organization=organization,
                    driver=driver,
                    truck=truck,
                    trailer=trailer,
                    date=date,
                    year=year,
                    number=last_number + 1,
                )

                # Прогоняем валидацию модели перед сохранением.
                waybill.full_clean()
                waybill.save(force_insert=True)

                return waybill

        except IntegrityError:
            # Если в параллельном запросе уже заняли этот номер,
            # пробуем пересчитать и сохранить ещё раз.
            if attempt == 4:
                raise
