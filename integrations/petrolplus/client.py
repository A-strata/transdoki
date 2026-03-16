from __future__ import annotations

from datetime import date
from urllib.parse import urljoin

import requests

from .auth import PetrolPlusAuthClient
from .exceptions import PetrolPlusAPIError


class PetrolPlusAPIClient:
    def __init__(
        self,
        *,
        data_base_url: str,
        auth_client: PetrolPlusAuthClient,
        timeout: int = 15,
    ) -> None:
        self.data_base_url = data_base_url.rstrip("/") + "/"
        self.auth_client = auth_client
        self.timeout = timeout

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
        response = self._do_http_request(
            method, path, token=token, params=params)

        if response.status_code == 401 and retry_on_401:
            token = self.auth_client.get_access_token(force_refresh=True)
            response = self._do_http_request(
                method, path, token=token, params=params)

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
            raise PetrolPlusAPIError(
                "API PetrolPlus вернул не-JSON ответ") from exc

    def _do_http_request(
            self,
            method: str,
            path: str,
            *,
            token: str,
            params: dict | None
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
            raise PetrolPlusAPIError(
                "Сетевой сбой при обращении к API PetrolPlus") from exc
