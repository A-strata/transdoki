from __future__ import annotations

import logging
from urllib.parse import urljoin

import requests
from django.core.cache import cache

from .exceptions import PetrolPlusAuthError

logger = logging.getLogger(__name__)


class PetrolPlusAuthClient:
    def __init__(
        self,
        *,
        auth_base_url: str,
        token_path: str,
        client_id: str,
        client_secret: str,
        timeout: int = 15,
        cache_key: str = "petrolplus:access_token",
        ttl_safety_buffer: int = 30,
    ) -> None:
        self.auth_base_url = auth_base_url.rstrip("/") + "/"
        self.token_path = token_path.lstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self.cache_key = cache_key
        self.ttl_safety_buffer = ttl_safety_buffer

    def get_access_token(self, force_refresh: bool = False) -> str:
        if not force_refresh:
            token = cache.get(self.cache_key)
            if token:
                return token

        token, expires_in = self._request_token()
        cache_ttl = max(1, int(expires_in) - self.ttl_safety_buffer)
        cache.set(self.cache_key, token, timeout=cache_ttl)
        return token

    def _request_token(self) -> tuple[str, int]:
        url = urljoin(self.auth_base_url, self.token_path)

        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        try:
            response = requests.post(
                url, data=data, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            logger.exception("PetrolPlus auth request failed")
            raise PetrolPlusAuthError(
                "Не удалось выполнить запрос к auth API PetrolPlus") from exc

        if response.status_code != 200:
            payload = {}
            try:
                payload = response.json()
            except ValueError:
                pass
            raise PetrolPlusAuthError(
                ("Ошибка авторизации PetrolPlus: HTTP "
                 F"{response.status_code}, payload={payload}")
            )

        try:
            payload = response.json()
            token = payload["access_token"]
            expires_in = int(payload.get("expires_in", 300))
        except (ValueError, KeyError, TypeError) as exc:
            raise PetrolPlusAuthError(
                "Некорректный формат ответа auth API PetrolPlus") from exc

        return token, expires_in
