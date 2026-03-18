# integrations/petrolplus/services.py
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from .client import PetrolPlusAPIClient
from .exceptions import PetrolPlusAPIError

if TYPE_CHECKING:
    from organizations.models import Organization


def get_current_balance(org: "Organization") -> Decimal:
    client = PetrolPlusAPIClient(org)
    payload = client.get_balance()  # сырой JSON от провайдера

    try:
        return Decimal(str(payload["balance"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise PetrolPlusAPIError("Некорректный формат баланса от PetrolPlus") from exc
