from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.views.generic import ListView

from transdoki.tenancy import get_request_account


class FilteredSortedListMixin:
    """
    Миксин для ListView: поиск по q, сортировка sort/dir, пагинация, query_string.

    Подкласс задаёт:
        search_fields: tuple[str]   — поля для icontains (OR-join)
        sort_fields:   tuple[str]   — допустимые значения параметра sort
        default_sort:  str          — дефолтное поле сортировки
        default_sort_dir: "asc" | "desc"

    При необходимости переопределяет:
        apply_extra_filters(qs) — дополнительная фильтрация (status и т.п.)
        get_extra_filter_params() — {name: value} для query_string

    В get_queryset нужно вызвать self.apply_filters_and_sort(qs) после
    построения базового queryset с tenant-фильтром.

    В get_context_data можно вызвать self.get_filter_context() и обновить
    контекст: он вернёт filters / query_string / sort_urls / page_size_options.
    """

    search_fields: tuple[str, ...] = ()
    sort_fields: tuple[str, ...] = ()
    default_sort: str = ""
    default_sort_dir: str = "desc"

    def get_search_query(self) -> str:
        return self.request.GET.get("q", "").strip()

    def parse_sort(self) -> tuple[str, str]:
        sort = self.request.GET.get("sort", self.default_sort).strip()
        direction = self.request.GET.get("dir", self.default_sort_dir).strip()
        if sort not in self.sort_fields:
            sort = self.default_sort
        if direction not in ("asc", "desc"):
            direction = self.default_sort_dir
        return sort, direction

    def apply_search(self, qs):
        q = self.get_search_query()
        if q and self.search_fields:
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f"{field}__icontains": q})
            qs = qs.filter(query)
        return qs

    def apply_extra_filters(self, qs):
        """Переопределить в подклассе для status/date/etc."""
        return qs

    def apply_sort(self, qs):
        sort, direction = self.parse_sort()
        order = sort if direction == "asc" else f"-{sort}"
        # -pk как вторичный ключ — стабильный порядок при совпадении значений.
        return qs.order_by(order, "-pk")

    def apply_filters_and_sort(self, qs):
        qs = self.apply_search(qs)
        qs = self.apply_extra_filters(qs)
        qs = self.apply_sort(qs)
        return qs

    def get_extra_filter_params(self) -> dict[str, str]:
        """Переопределить при наличии доп. GET-параметров (status, и пр.)."""
        return {}

    def _base_url_params(self) -> dict[str, str]:
        """Параметры, влияющие на содержимое страницы (без page).

        Используется в query_string для пагинации и в sort_urls.
        Включает только не-дефолтные значения, чтобы URL оставались чистыми.
        """
        params: dict[str, str] = {}
        q = self.get_search_query()
        if q:
            params["q"] = q
        params.update(self.get_extra_filter_params())

        sort, direction = self.parse_sort()
        if sort != self.default_sort:
            params["sort"] = sort
        if direction != self.default_sort_dir:
            params["dir"] = direction

        current_page_size = self.get_paginate_by(self.object_list)
        if str(current_page_size) != str(self.paginate_by):
            params["page_size"] = str(current_page_size)

        return params

    def _build_sort_url(self, field: str) -> str:
        sort, direction = self.parse_sort()
        params = dict(self._base_url_params())
        params["sort"] = field
        params["dir"] = (
            "desc" if (field == sort and direction == "asc") else "asc"
        )
        return "?" + urlencode(params)

    def get_filter_context(self) -> dict:
        sort, direction = self.parse_sort()
        current_page_size = self.get_paginate_by(self.object_list)
        base_params = self._base_url_params()

        filters = {
            "q": self.get_search_query(),
            "sort": sort,
            "dir": direction,
            "page_size": str(current_page_size),
            **self.get_extra_filter_params(),
        }

        return {
            "filters": filters,
            "query_string": ("&" + urlencode(base_params)) if base_params else "",
            "sort_urls": {f: self._build_sort_url(f) for f in self.sort_fields},
            "page_size_options": self.page_size_options,
        }


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
