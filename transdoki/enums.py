from django.db import models


class VatRate(models.IntegerChoices):
    """Ставки НДС РФ. Единый источник для всех приложений."""
    ZERO       = 0,  "0%"
    FIVE       = 5,  "5%"
    SEVEN      = 7,  "7%"
    TEN        = 10, "10%"
    TWENTY_TWO = 22, "22%"
