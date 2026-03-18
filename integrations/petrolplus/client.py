from __future__ import annotations

from datetime import date
from urllib.parse import urljoin
from typing import TYPE_CHECKING

import requests
from django.conf import settings

from .auth import PetrolPlusAuthClient
from .exceptions import PetrolPlusAPIError

if TYPE_CHECKING:
    from organizations.models import Organization


class PetrolPlusAPIClient:
    def __init__(self, org: "Organization", timeout: int | None = None) -> None:
        if not org.petrolplus_integration_enabled:
            raise ValueError("Интеграция PetrolPlus отключена для организации")

        if not org.petrolplus_client_id or not org.petrolplus_client_secret:
            raise ValueError("Не заполнены petrolplus_client_id / petrolplus_client_secret")

        self.org = org
        self.timeout = timeout or settings.PETROLPLUS_TIMEOUT
        self.data_base_url = settings.PETROLPLUS_DATA_URL.rstrip("/") + "/"

        self.auth_client = PetrolPlusAuthClient(
            auth_base_url=settings.PETROLPLUS_AUTH_BASE_URL,
            token_path=settings.PETROLPLUS_TOKEN_PATH,
            client_id=org.petrolplus_client_id,
            client_secret=org.petrolplus_client_secret,  # ORM расшифрует автоматически
            timeout=self.timeout,
            cache_key=f"petrolplus:access_token:org:{org.id}",
        )

    def get_balance(self) -> dict:
        return self._request("GET", "balance")

    def get_transactions(self, *, date_from: date, date_to: date) -> dict:
        params = {
            "dateFrom": date_from.isoformat(),
            "dateTo": date_to.isoformat(),
        }
        return self._request("GET", "transactions", params=params)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        retry_on_401: bool = True,
    ) -> dict:
        token = self.auth_client.get_access_token()
        response = self._do_http_request(method, path, token=token, params=params)

        if response.status_code == 401 and retry_on_401:
            token = self.auth_client.get_access_token(force_refresh=True)
            response = self._do_http_request(method, path, token=token, params=params)

        if not response.ok:
            payload = {}
            try:
                payload = response.json()
            except ValueError:
                pass

            raise PetrolPlusAPIError(
                f"Ошибка API PetrolPlus: HTTP {response.status_code}",
                status_code=response.status_code,
                payload=payload,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise PetrolPlusAPIError("API PetrolPlus вернул не-JSON ответ") from exc

    def _do_http_request(
        self,
        method: str,
        path: str,
        *,
        token: str,
        params: dict | None,
    ) -> requests.Response:
        url = urljoin(self.data_base_url, path.lstrip("/"))
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        try:
            return requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise PetrolPlusAPIError("Сетевой сбой при обращении к API PetrolPlus") from exc
