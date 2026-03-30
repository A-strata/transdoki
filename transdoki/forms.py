class ErrorHighlightMixin:
    """Добавляет CSS-класс ``is-invalid`` к виджетам полей с ошибками.

    Подключается первым в MRO::

        class MyForm(ErrorHighlightMixin, forms.ModelForm):
            ...

    После вызова ``is_valid()`` (или при повторном рендере формы с
    ошибками) Django автоматически проставит ``is-invalid`` на ``<input>``/
    ``<select>``/``<textarea>`` — браузер отрисует красную рамку без JS.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._highlight_errors()

    def _highlight_errors(self):
        for field_name in self.errors:
            if field_name in self.fields:
                widget = self.fields[field_name].widget
                cls = widget.attrs.get("class", "")
                if "is-invalid" not in cls:
                    widget.attrs["class"] = (cls + " is-invalid").strip()
