# integrations/petrolplus/services.py

from decimal import Decimal
from . import get_petrolplus_client
from .exceptions import PetrolPlusAPIError


def get_current_balance() -> Decimal:
    client = get_petrolplus_client()
    payload = client.get_balance()  # сырой JSON от провайдера

    try:
        return Decimal(str(payload["balance"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise PetrolPlusAPIError(
            "Некорректный формат баланса от PetrolPlus") from exc
