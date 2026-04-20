# Бриф: унификация лимита «Свои организации» с паттерном «Профиль и команда»

**Версия:** 1.0
**Дата:** 20.04.2026
**Автор:** продуктовый дизайн
**Исполнитель:** Claude Code
**Связано:** `docs/cabinet-team-redesign-spec.md` v1.3 (паттерн `can_invite` → CTA «Увеличить лимит»)

---

## Цель

Привести UX «Свои организации» к тому же паттерну «prevent», что и блок «Профиль и команда» в ЛК v1.3:

- При **исчерпанном лимите собственных компаний** primary-кнопка «+ Добавить компанию» **заменяется** на secondary-кнопку «Увеличить лимит →» (ведёт на `billing:subscription`).
- Контрагенты не лимитируются — кнопка «+ Добавить контрагента» всегда активна.
- Тост и редирект на список контрагентов уходят с happy-path. `OrganizationCreateView` остаётся защитой от прямого URL.

## Проблема (текущее поведение)

1. `organizations/templates/organizations/organization_list.html:32` — кнопка «+ Добавить компанию» рендерится безусловно, без учёта `can_create_organization(account)`.
2. `organizations/views.py:39-48` — при превышении лимита делает `redirect("organizations:list")` (общий список, по дефолту контрагенты) + `messages.error`. Пользователь из вкладки «Мои компании» оказывается на «Контрагентах» с тостом — двойная потеря контекста.
3. В `templates/base.html:179` ссылка «Добавить компанию» в сайдбаре тоже безусловная.
4. Счётчика «N из M собственных компаний» нигде не видно — пользователь упирается в стену внезапно.

## Решение

### 1. Контекст в `OrganizationListView` и `OwnCompanyListView`

В `get_context_data` добавить:

```python
from billing.services.limits import can_create_organization

ctx["can_create_own_org"], _ = can_create_organization(account)

subscription = getattr(account, "subscription", None)
ctx["org_limit"] = subscription.effective_org_limit if subscription else None
ctx["org_count_current"] = (
    Organization.objects.for_account(account)
    .filter(is_own_company=True)
    .count()
)
```

`can_create_organization` уже корректно обрабатывает exempt-аккаунты, отсутствующую подписку и `is_billing_exempt` — повторно не валидируем.

### 2. Шаблон `organization_list.html` — кнопка-CTA

Заменить безусловную кнопку (строка 32) на ветвление по `is_own` + `can_create_own_org`:

```django
{% if is_own %}
  {% if can_create_own_org %}
    <a href="{% url 'organizations:create' %}?own=1"
       class="tms-btn tms-btn-primary tms-btn-add">+ Добавить компанию</a>
  {% else %}
    <a href="{% url 'billing:subscription' %}"
       class="tms-btn tms-btn-secondary"
       title="Лимит собственных организаций исчерпан">Увеличить лимит →</a>
  {% endif %}
{% else %}
  <a href="{% url 'organizations:create' %}"
     class="tms-btn tms-btn-primary tms-btn-add">+ Добавить контрагента</a>
{% endif %}
```

### 3. Шаблон — счётчик в шапке

Под `<h1>{% if is_own %}Мои компании{% endif %}</h1>` (только при `is_own`) добавить мелкий счётчик:

```django
{% if is_own and org_limit %}
  <p class="list-toolbar-meta lk-small lk-muted">
    {{ org_count_current }} из {{ org_limit }} собственных организаций по тарифу.
  </p>
{% elif is_own %}
  <p class="list-toolbar-meta lk-small lk-muted">
    {{ org_count_current }} собственных организаций. Без ограничений по тарифу.
  </p>
{% endif %}
```

CSS-класс `list-toolbar-meta` — добавить в существующий `organization_list.css`:
```css
.list-toolbar-meta { margin: 4px 0 0; font-size: var(--text-xs); color: var(--muted); }
```

### 4. Сайдбар `templates/base.html:179` — ту же логику

Если ссылка-плюсик «Добавить компанию» в сайдбаре доступна на любой странице (не только в list view), нужно прокидывать `can_create_own_org` через context-processor — иначе ветвление не сработает.

Простейший вариант: завести context-processor `billing.context_processors.org_limits` и подключить его в `settings.TEMPLATES`. Возвращает `{"can_create_own_org": bool, "org_limit": int|None, "org_count_current": int}` для каждого запроса аутентифицированного пользователя.

Если такого context-processor пока нет — **остановиться и согласовать**, не плодить дублирование query на каждом запросе.

### 5. `OrganizationCreateView.dispatch` — hotfix редиректа

Логика остаётся (защита от прямого URL), но редирект корректный:

```python
def dispatch(self, request, *args, **kwargs):
    if request.user.is_authenticated and self._is_own():
        account = get_request_account(request)
        ok, msg = can_create_organization(account)
        if not ok:
            messages.error(request, msg)
            referer = request.META.get("HTTP_REFERER")
            if referer:
                return redirect(referer)
            return redirect("organizations:own_list")
    return super().dispatch(request, *args, **kwargs)
```

Изменения относительно текущего:
- `redirect("organizations:list")` → `redirect("organizations:own_list")` (не бросать в контрагенты).
- Перед фолбэком — попытка `HTTP_REFERER` (вернуться откуда пришёл).

### 6. `trips/trip_form.html` quick-create модалка

Quick-create в trip_form создаёт **контрагента** (не own-компанию) — лимит на него не распространяется. Изменений не требуется. Но имеет смысл проверить, что `organization_quick_create` view не пытается применить лимит — если пытается, ослабить.

Проверочный grep: `grep -n "can_create_organization\|is_own" organizations/views.py | head -20` — убедиться, что в `organization_quick_create` лимит **не** проверяется (контрагенты лимиту не подлежат).

## Файлы

| Файл | Что меняем |
|---|---|
| `organizations/views.py` | (а) `OrganizationListView.get_context_data` + `OwnCompanyListView.get_context_data` — добавить `can_create_own_org`, `org_limit`, `org_count_current`. (б) `OrganizationCreateView.dispatch` — фикс редиректа. |
| `organizations/templates/organizations/organization_list.html` | Ветвление кнопки + счётчик в шапке. |
| `organizations/static/organizations/css/organization_list.css` | `.list-toolbar-meta`. |
| `templates/base.html` | Ветвление ссылки в сайдбаре (если context-processor подключаем). |
| `billing/context_processors.py` (опционально) | Новый processor `org_limits`. **Если файла нет — остановиться и согласовать.** |
| `settings.py` (опционально) | Подключение processor'а в `TEMPLATES.OPTIONS.context_processors`. |
| `organizations/tests.py` | Тест на ветвление контекста: при `org_count == org_limit` → `can_create_own_org=False`; при `org_count < org_limit` → `True`; для контрагентов кнопка не зависит от `can_create_own_org`. |
| `organizations/tests.py` | Тест на dispatch: при превышении лимита и наличии `HTTP_REFERER` → redirect на referer; без referer → `own_list`. |

## Acceptance criteria

1. На `/organizations/own/` (или `/organizations/?own=1`) при `org_count < org_limit` отображается primary-кнопка «+ Добавить компанию».
2. На той же странице при `org_count == org_limit` (лимит исчерпан) primary-кнопка **заменена** на secondary `Увеличить лимит →`, ведущую на `/billing/subscription/`.
3. На `/organizations/` (контрагенты) primary-кнопка «+ Добавить контрагента» отображается всегда независимо от `org_count`.
4. В шапке списка собственных под заголовком виден счётчик `{N} из {M} собственных организаций по тарифу`. На контрагентах счётчика нет.
5. Прямой URL `/organizations/create/?own=1` при исчерпанном лимите редиректит на `HTTP_REFERER`, если он есть, иначе — на `organizations:own_list` (НЕ на `organizations:list`). Тост `messages.error` сохраняется.
6. Клик на «+ Добавить контрагента» через `quick_create` (модалка из trip_form) работает при **любом** значении `org_count_current` для own-компаний — контрагенты не подпадают под лимит.
7. Exempt-аккаунты (`is_billing_exempt=True`) видят primary-кнопку «+ Добавить компанию» всегда, независимо от `org_count`.
8. Аккаунты без подписки (free tier) — поведение симметрично команде: лимит из `FREE_TIER_*` или дефолта подписки.
9. `python manage.py test organizations` проходит, в т.ч. два новых теста.
10. `ruff check .` зелёный.
11. Никаких новых миграций. Никаких новых зависимостей. `accounts/views.py` не трогаем.

## Open questions (если возникнут)

Если в процессе обнаружится одно из:
- `billing.context_processors` модуля нет, и заводить его кажется избыточным ради одного флага в сайдбаре — **остановиться, доложить**. Альтернатива — оставить ссылку в сайдбаре безусловной как раньше, ограничив унификацию только страницами списка. Это половинчатое решение, но допустимое.
- `organization_quick_create` (контрагенты в trip_form) внезапно вызывает `can_create_organization` — **остановиться, доложить**: контрагенты не должны лимитироваться, надо смотреть, не баг ли это уже сейчас.
- `subscription.effective_org_limit` отсутствует или возвращает не то, что ожидается — **остановиться, доложить**.

Не принимать решения молча.

## Definition of done

- Из ЛК / `/organizations/own/` пользователь с исчерпанным лимитом видит кнопку «Увеличить лимит →», а не редирект на контрагентов с тостом.
- Из любого list-view собственных видно текущее `N из M`.
- Прямой URL `/organizations/create/?own=1` при лимите ведёт обратно (на referer или `own_list`), не в контрагенты.
- Поведение exempt-аккаунтов и free tier — без регрессий.
- Все три теста зелёные (`ruff` + два новых юнит-теста + тест dispatch).
