"""
Тест мультитенантной изоляции: все CBV, работающие с моделями-наследниками
UserOwnedModel, обязаны фильтровать данные по тенанту.

Два вида проверок:
  1. Views, читающие данные (List/Detail/Update/Delete) — get_queryset
     должен содержать фильтрацию по account или current_org.
  2. CreateView — form_valid должен проставлять account.

Запуск:
    python manage.py test tests.test_tenant_isolation
"""

import inspect

from django.test import SimpleTestCase
from django.urls import URLPattern, URLResolver, get_resolver
from django.views import View
from django.views.generic.edit import CreateView

from transdoki.models import UserOwnedModel

TENANT_MARKERS = ("account", "current_org")


def _collect_cbv_classes(urlpatterns, seen=None):
    """Рекурсивно собирает все CBV-классы из URL-конфигурации."""
    if seen is None:
        seen = set()
    for pattern in urlpatterns:
        if isinstance(pattern, URLResolver):
            _collect_cbv_classes(pattern.url_patterns, seen)
        elif isinstance(pattern, URLPattern):
            view_class = getattr(getattr(pattern, "callback", None), "view_class", None)
            if view_class and issubclass(view_class, View):
                seen.add(view_class)
    return seen


def _get_view_model(view_class):
    """Возвращает модель CBV (model или queryset.model)."""
    model = getattr(view_class, "model", None)
    if model is None:
        qs = getattr(view_class, "queryset", None)
        if qs is not None:
            model = qs.model
    return model


def _method_has_tenant_filter(view_class, method_name):
    """
    Проходит по MRO и ищет method_name с tenant-фильтрацией.
    Правила:
      - Пропускаем базовые Django-классы
      - Если метод содержит маркер tenant-фильтрации — ОК
      - Если метод вызывает super() — продолжаем вверх по MRO
      - Если метод есть, но без маркеров и без super() — нарушение
    """
    for cls in inspect.getmro(view_class):
        if cls.__module__.startswith("django."):
            return False
        if method_name not in cls.__dict__:
            continue
        source = inspect.getsource(cls.__dict__[method_name])
        if any(marker in source for marker in TENANT_MARKERS):
            return True
        if "super()" in source:
            continue
        return False
    return False


class TenantIsolationTest(SimpleTestCase):
    """
    Для каждого CBV с UserOwnedModel-моделью проверяем tenant-изоляцию:
    - CreateView: form_valid проставляет account
    - Остальные: get_queryset фильтрует по account/current_org
    """

    def test_read_views_filter_by_tenant(self):
        all_views = _collect_cbv_classes(get_resolver().url_patterns)
        violations = []

        for view_class in sorted(all_views, key=lambda v: v.__qualname__):
            model = _get_view_model(view_class)
            if model is None or not issubclass(model, UserOwnedModel):
                continue
            if issubclass(view_class, CreateView):
                continue
            if not _method_has_tenant_filter(view_class, "get_queryset"):
                violations.append(
                    f"  {view_class.__module__}.{view_class.__qualname__}"
                    f" (model={model.__name__})"
                )

        self.assertEqual(
            violations,
            [],
            "Views без tenant-фильтрации в get_queryset:\n"
            + "\n".join(violations),
        )

    def test_create_views_set_account(self):
        all_views = _collect_cbv_classes(get_resolver().url_patterns)
        violations = []

        for view_class in sorted(all_views, key=lambda v: v.__qualname__):
            model = _get_view_model(view_class)
            if model is None or not issubclass(model, UserOwnedModel):
                continue
            if not issubclass(view_class, CreateView):
                continue
            has_filter = (
                _method_has_tenant_filter(view_class, "form_valid")
                or _method_has_tenant_filter(view_class, "post")
            )
            if not has_filter:
                violations.append(
                    f"  {view_class.__module__}.{view_class.__qualname__}"
                    f" (model={model.__name__})"
                )

        self.assertEqual(
            violations,
            [],
            "CreateView без присвоения account в form_valid:\n"
            + "\n".join(violations),
        )
