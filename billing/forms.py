from django import forms

from .cloudpayments import MAX_DEPOSIT_AMOUNT, MIN_DEPOSIT_AMOUNT


class DepositForm(forms.Form):
    amount = forms.DecimalField(
        label="Сумма пополнения (₽)",
        min_value=MIN_DEPOSIT_AMOUNT,
        max_value=MAX_DEPOSIT_AMOUNT,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            "placeholder": "Например, 500",
            "step": "1",
            "autofocus": True,
        }),
        error_messages={
            "min_value": f"Минимальная сумма — {MIN_DEPOSIT_AMOUNT} ₽.",
            "max_value": f"Максимальная сумма — {MAX_DEPOSIT_AMOUNT:,.0f} ₽.",
            "invalid": "Введите корректную сумму.",
        },
    )
