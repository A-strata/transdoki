from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from transdoki.tenancy import get_request_account


class UserOwnedListView(LoginRequiredMixin, ListView):
    """Базовый ListView — показывает только записи текущего account (tenant)."""

    paginate_by = 25
    page_size_options = [25, 50, 100]

    def get_paginate_by(self, queryset):
        raw = (self.request.GET.get("page_size") or "").strip()
        if raw.isdigit():
            value = int(raw)
            if value in self.page_size_options:
                return value
        return self.paginate_by

    def get_queryset(self):
        return self.model.objects.for_account(get_request_account(self.request))

    def _build_pagination_items(self, page_obj):
        current = page_obj.number
        total = page_obj.paginator.num_pages

        if total <= 7:
            return [
                {"type": "page", "number": n, "current": n == current}
                for n in range(1, total + 1)
            ]

        pages = {1, total, current - 2, current - 1, current, current + 1, current + 2}
        pages = sorted(n for n in pages if 1 <= n <= total)

        items = []
        prev = None

        for n in pages:
            if prev is not None and n - prev > 1:
                items.append({"type": "ellipsis"})
            items.append({"type": "page", "number": n, "current": n == current})
            prev = n

        return items
