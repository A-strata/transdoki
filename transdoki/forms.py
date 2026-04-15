from django import forms


class LocalizedDecimalFormMixin:
    """Локализует все ``DecimalField`` формы под русскую раскладку.

    Автоматически находит каждое DecimalField и:

    - включает ``localize=True`` (Django принимает и ``"0,5"``, и ``"0.5"``,
      обратно рендерит с запятой);
    - переводит виджет в ``input_type="text"`` + ``inputmode="decimal"`` —
      браузерный ``type="number"`` несовместим с русской запятой и на
      мобильных клавиатурах молча отбрасывает её.

    Подключать **первым** в MRO, как и ErrorHighlightMixin::

        class InvoiceForm(LocalizedDecimalFormMixin, ErrorHighlightMixin,
                          forms.ModelForm):
            ...

    Причина существования миксина — инцидент с рейсом №9: ставка
    ``0,5 руб/кг`` молча не сохранялась из-за ``type="number"``. Теперь
    любая новая форма с денежными/количественными полями получает
    корректный ввод бесплатно, без дублирования кода.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field, forms.DecimalField):
                continue
            field.localize = True
            field.widget.is_localized = True
            field.widget.input_type = "text"
            attrs = field.widget.attrs
            attrs.setdefault("inputmode", "decimal")
            attrs.setdefault("autocomplete", "off")


class ErrorHighlightMixin:
    """Добавляет CSS-класс ``is-invalid`` к виджетам полей с ошибками.

    Подключается первым в MRO::

        class MyForm(ErrorHighlightMixin, forms.ModelForm):
            ...

    Подсветка применяется лениво — при обращении к ``errors`` (через
    ``is_valid()`` или рендер шаблона), а не в ``__init__``. Это гарантирует,
    что подклассы успеют сконфигурировать поля (кастомные queryset'ы,
    AJAX-поля) до первого запуска валидации.
    """

    @property
    def errors(self):
        result = super().errors
        self._highlight_errors()
        return result

    def _highlight_errors(self):
        if not hasattr(self, "_errors") or self._errors is None:
            return
        for field_name in self._errors:
            if field_name in self.fields:
                widget = self.fields[field_name].widget
                cls = widget.attrs.get("class", "")
                if "is-invalid" not in cls:
                    widget.attrs["class"] = (cls + " is-invalid").strip()
