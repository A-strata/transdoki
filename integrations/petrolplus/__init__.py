from django.conf import settings
from .auth import PetrolPlusAuthClient
from .client import PetrolPlusAPIClient


def get_petrolplus_client_for_org(org):
    auth_client = PetrolPlusAuthClient(
        auth_base_url=settings.PETROLPLUS_AUTH_BASE_URL,
        token_path=settings.PETROLPLUS_TOKEN_PATH,
        client_id=org.petrolplus_client_id,
        client_secret=org.petrolplus_client_secret,
        timeout=settings.PETROLPLUS_TIMEOUT,
        cache_key=f"petrolplus:access_token:org:{org.id}",
    )
    return PetrolPlusAPIClient(
        data_base_url=settings.PETROLPLUS_DATA_URL,
        auth_client=auth_client,
        timeout=settings.PETROLPLUS_TIMEOUT,
    )
