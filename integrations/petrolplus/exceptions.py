class PetrolPlusError(Exception):
    """Базовая ошибка интеграции PetrolPlus."""


class PetrolPlusAuthError(PetrolPlusError):
    """Ошибка получения/обновления токена."""


class PetrolPlusAPIError(PetrolPlusError):
    """Ошибка вызова бизнес-методов API."""

    def __init__(
            self,
            message: str,
            status_code: int | None = None,
            payload: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}
