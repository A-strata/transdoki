from django.conf import settings

from .auth import PetrolPlusAuthClient
from .client import PetrolPlusAPIClient


def get_petrolplus_client() -> PetrolPlusAPIClient:
    auth_base_url = getattr(settings, "PETROLPLUS_AUTH_BASE_URL", None) or getattr(settings, "PETROLPLUS_BASE_URL", None)
    data_base_url = getattr(settings, "PETROLPLUS_DATA_URL", None)
    token_path = getattr(settings, "PETROLPLUS_TOKEN_PATH", None)
    client_id = getattr(settings, "PETROLPLUS_CLIENT_ID", None)
    client_secret = getattr(settings, "PETROLPLUS_CLIENT_SECRET", None)
    timeout = int(getattr(settings, "PETROLPLUS_TIMEOUT", 15))

    missing = [
        name for name, value in [
            ("PETROLPLUS_AUTH_BASE_URL / PETROLPLUS_BASE_URL", auth_base_url),
            ("PETROLPLUS_DATA_URL", data_base_url),
            ("PETROLPLUS_TOKEN_PATH", token_path),
            ("PETROLPLUS_CLIENT_ID", client_id),
            ("PETROLPLUS_CLIENT_SECRET", client_secret),
        ] if not value
    ]
    if missing:
        raise RuntimeError(f"PetrolPlus integration misconfigured. Missing: {', '.join(missing)}")

    auth_client = PetrolPlusAuthClient(
        auth_base_url=auth_base_url,
        token_path=token_path,
        client_id=client_id,
        client_secret=client_secret,
        timeout=timeout,
    )
    return PetrolPlusAPIClient(
        data_base_url=data_base_url,
        auth_client=auth_client,
        timeout=timeout,
    )