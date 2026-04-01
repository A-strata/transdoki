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
