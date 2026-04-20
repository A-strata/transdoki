# Бриф для Claude Code — применение ТЗ v1.3

**Контекст:** версия 1.0 была частично реализована, в текущем `accounts/templates/accounts/cabinet.html` остались её артефакты (отдельная `.lk-self-card`, чип «это вы», подстрочник, инлайн-селект роли) плюс регрессия «сброс работает один раз + kebab над модалкой». Версия 1.3 заменяет ту реализацию целиком и лечит регрессию.

Полная спецификация — `docs/cabinet-team-redesign-spec.md` (v1.3).
Эталон вёрстки — `cabinet-mockup.html` (блок «Профиль и команда», обновлён под v1.3).

**Что новое в v1.3 (относительно v1.2):** self-row использует kebab (а не две inline-кнопки) для единообразия с остальными строками. Подробнее — ниже в §1.

---

## Ключевые отличия от того, что сейчас в шаблоне

| Было (v1.0/1.1 в реализации) | Стало (v1.3) |
|---|---|
| Отдельная `.lk-self-card` с чипом «это вы» и подстрочником | Self-row — первая строка `.lk-team-list` с классом `is-self`, без чипа, без подстрочника |
| Отдельная колонка статуса (`.lk-team-status` с `lk-chip--ok/warn`) | Статус — словом в мета-строке, подсветка только для не-активных состояний |
| Чип роли рядом с ФИО в каждой строке | Роль — словом в мета-строке. Чип остаётся только в self-row у владельца (`lk-role-chip--owner`) |
| Инлайн-селект роли с instant-save и toast-undo | Удалён. Роль меняется в модалке `edit-user-modal` одним POST'ом вместе с ФИО |
| Подзаголовок `<h4>Сотрудники</h4>` | Убрали. Список идёт сразу под шапкой карточки |
| Счётчик «N из M» в шапке + отдельный подстрочник про сброс | Одно предложение футера: «N из M по тарифу «Бизнес». Сверх лимита — rate ₽/сутки за пользователя» |
| Kebab у команды + иногда ломался поверх модалки | Kebab сохраняется (три пункта), но `openModal` форсирует закрытие всех kebab'ов |
| Self-row: две inline-кнопки «Изменить» + «Сменить пароль» | Self-row: kebab с двумя пунктами «Редактировать профиль…» + «Сменить пароль» (для единообразия) |

---

## 1. Правки в `accounts/templates/accounts/cabinet.html`

Переверстать блок «Профиль и команда» целиком. Каркас — см. §3 спецификации и мокап.

Шаблон self-row (kebab для единообразия с team-rows):

```django
<div class="lk-team-row is-self">
  <div class="lk-avatar">{{ self_initials }}</div>
  <div class="lk-team-meta">
    <div class="lk-team-name">
      {{ request.user.get_full_name|default:request.user.username }}
      <span class="lk-role-chip{% if profile.role == 'owner' %} lk-role-chip--owner{% endif %}">
        {{ profile.get_role_display }}
      </span>
    </div>
    <div class="lk-team-info">
      {{ request.user.email|default:request.user.username }}
      {% if request.user.last_login %} · последний вход {{ request.user.last_login|date:"j M, H:i" }}{% endif %}
    </div>
  </div>
  <div class="lk-actions-cell">
    <button class="lk-kebab" type="button" aria-label="Действия" data-kebab-toggle>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/></svg>
    </button>
    <div class="lk-kebab-menu" hidden>
      <button type="button" class="lk-kebab-item" data-lk-modal-open="edit-self-modal">Редактировать профиль…</button>
      <a class="lk-kebab-item" href="{% url 'password_change' %}">Сменить пароль</a>
    </div>
  </div>
</div>
```

Важно: у self-kebab только 2 пункта, без divider'а и «Отключить пользователя (скоро)». «Сменить пароль» — это `<a>`, а не `<button>` (ведёт на встроенный Django-view `PasswordChangeView`). В базовом стиле `.lk-kebab-item` должно быть `text-decoration:none`, чтобы ссылка не подчёркивалась и визуально не отличалась от остальных пунктов.

Шаблон team-row (всё — одной мета-строкой, kebab справа):

```django
{% for p in users_in_account %}
  {% with status=p|team_status role_word=p.get_role_display|lower %}
  <div class="lk-team-row" id="user-{{ p.id }}" data-profile-id="{{ p.id }}" data-role="{{ p.role }}">
    <div class="lk-avatar">{{ p|initials }}</div>
    <div class="lk-team-meta">
      <div class="lk-team-name">{{ p.user.get_full_name|default:p.user.username }}</div>
      <div class="lk-team-info">
        {{ p.user.email|default:p.user.username }} · {{ role_word }} ·
        {% if status == 'active' %}активен
        {% elif status == 'pending' %}<span class="lk-meta-warn">ожидает входа</span>
        {% elif status == 'off' %}<span class="lk-meta-off">отключён</span>
        {% endif %}
      </div>
    </div>
    {% if can_manage_users and p.role != 'owner' and p.user_id != request.user.id %}
      <div class="lk-actions-cell">
        <button class="lk-kebab" type="button" aria-label="Действия" data-kebab-toggle>
          <svg …><!-- три точки --></svg>
        </button>
        <div class="lk-kebab-menu" hidden>
          <button type="button" class="lk-kebab-item"
                  data-lk-modal-open="edit-user-modal"
                  data-profile-id="{{ p.id }}"
                  data-first-name="{{ p.user.first_name }}"
                  data-last-name="{{ p.user.last_name }}"
                  data-full-name="{{ p.user.get_full_name|default:p.user.username }}"
                  data-login="{{ p.user.email|default:p.user.username }}"
                  data-role="{{ p.role }}">Редактировать…</button>
          <button type="button" class="lk-kebab-item is-warn"
                  data-lk-modal-open="reset-confirm-modal"
                  data-profile-id="{{ p.id }}"
                  data-full-name="{{ p.user.get_full_name|default:p.user.username }}"
                  data-login="{{ p.user.email|default:p.user.username }}"
                  data-role-display="{{ p.get_role_display }}">Сбросить пароль</button>
          <div class="lk-kebab-divider"></div>
          <button type="button" class="lk-kebab-item" disabled title="Скоро">Отключить пользователя <span class="lk-soon">скоро</span></button>
        </div>
      </div>
    {% endif %}
  </div>
  {% endwith %}
{% endfor %}
```

Вместо `team_status`/`initials` template-tags — можно аннотировать в `AccountCabinetView.get_context_data` (аннотация `last_activity` уже там; добавить `status_code` одной строкой или оставить вычисление статуса в шаблоне через `{% if %}`).

### Что удалить из шаблона

- `<div class="lk-self-card">…</div>` целиком.
- `<p class="lk-self-footnote">` целиком.
- Внутри каждой `.lk-team-row` — `<div class="lk-team-status">` с `lk-chip--ok/warn`.
- Внутри `.lk-team-name` у team-rows — `<span class="lk-role-chip">…</span>` (роль уходит в мета-строку).
- `<h4>Сотрудники</h4>` + `.lk-team-head`.
- `<div class="lk-role-wrap">` со всем содержимым (`lk-role-select`, `lk-role-pill`).
- Чип «это вы» внутри self-row.

### Футер карточки

```django
<p class="lk-small lk-muted" style="margin:14px 0 0">
  {% if user_limit %}
    {{ user_count_current }} из {{ user_limit }} пользователей{% if subscription %} по тарифу «{{ subscription.plan.name }}»{% endif %}.
    При превышении лимита создание новых сотрудников блокируется — увеличьте лимит в тарифе.
  {% else %}
    {{ user_count_current }} пользователей в команде.
  {% endif %}
</p>
```

**`overage_per_user` в контекст не добавляем.** Billing v2 не начисляет посуточный overage по пользователям — при достижении лимита `can_invite=False` и `BillingProtectedMixin` блокирует создание. Константа `DAILY_RATE_USER` в `billing/constants.py` — legacy посуточного биллинга, удаляется в итерации 6, для футера не используется.

---

## 2. Правки в `accounts/templates/accounts/partials/cabinet_modals.html`

Переименовать `#edit-name-modal` → `#edit-user-modal` и добавить селект роли. См. мокап, строки модалки.

В `#edit-self-modal` поле «Роль» — read-only `lk-role-chip` (брендовый `--owner` для владельца, нейтральный для остальных). **Не** `lk-role-pill` (класс удалён).

---

## 3. Правки в `static/accounts/css/cabinet.css`

**Добавить из мокапа** (секция «Профиль и команда: единый список»):

- `.lk-team-list`.
- `.lk-team-row` — grid `32px minmax(0,1fr) auto`.
- `.lk-team-row.is-self`, `.lk-team-row.is-self + .lk-team-row`, `.lk-team-row.is-self .lk-team-name`, `.lk-team-row.is-self .lk-avatar`.
- `.lk-team-meta`, `.lk-team-name`, `.lk-team-info`.
- `.lk-meta-warn`, `.lk-meta-off`.
- `.lk-role-chip`, `.lk-role-chip--owner` (остаются — используются в self-row + в edit-self-modal).
- `.lk-actions-cell` (одна версия — без модификатора `--inline`; у self-row и team-row одинаковая).
- `.lk-kebab-item { text-decoration:none; color:inherit }` — чтобы `<a class="lk-kebab-item">` (пункт «Сменить пароль» в self-kebab) выглядел идентично `<button class="lk-kebab-item">`.
- Медиа-правило `@media (max-width:560px)` — grid для small-screen + уменьшенный self-avatar 36×36.

**Удалить полностью:**

- `.lk-self-card`, `.lk-self`, `.lk-self-head`, `.lk-self-meta`, `.lk-self-name`, `.lk-self-email`, `.lk-self-avatar`, `.lk-self-actions`, `.lk-self-sub`, `.lk-self-footnote`, `.lk-avatar--lg`.
- `.lk-role-cell`, `.lk-role-select` (все состояния, включая `is-saving`/`is-saved`), `.lk-role-pill` (все варианты).
- `.lk-team-head` (подзаголовок списка больше не нужен).
- `.lk-team-status` (если был выделен под колонку — убрать, колонки больше нет).
- `.lk-actions-cell--inline` (модификатор был в черновиках v1.2; в v1.3 не нужен — все actions-ячейки одинаковы).

---

## 4. Правки в `static/accounts/js/cabinet.js`

**Удалить:**
- `initInstantRoleSave()` и все обработчики `change` на `.lk-role-select[data-instant-save]`.
- В `showToast(opts)` — ветку с `opts.undo` и кнопкой «Отменить».

**Добавить / проверить:**

```js
// В openModal(id): принудительно закрыть все открытые kebab'ы.
function openModal(id){
  const overlay = document.getElementById(id);
  if(!overlay) return;
  closeAllKebabs();            // ← новая строка
  overlay.classList.add('is-open');
  // … focus trap, setup step=form и т.д.
}

// В closeModal(overlay): сбрасываем disabled и текст у всех submit'ов.
function closeModal(overlay){
  overlay.querySelectorAll('[data-submit-default-label]').forEach(btn => {
    btn.disabled = false;
    btn.textContent = btn.dataset.submitDefaultLabel;
  });
  overlay.classList.remove('is-open');
  // …
}
```

В `cabinet_modals.html` на кнопке сброса:
```html
<button type="submit" class="tms-btn tms-btn-primary"
        data-submit-default-label="Сбросить пароль">Сбросить пароль</button>
```

**`initEditUserFlow()`:**
- Слушать клик на `[data-lk-modal-open="edit-user-modal"]` у пункта kebab.
- Читать `data-profile-id`, `data-first-name`, `data-last-name`, `data-login`, `data-role`.
- Проставить значения в поля модалки (`#edit-user-fn`, `#edit-user-ln`, `#edit-user-role`, disabled-input с login, hidden input с profile-id).
- На submit — один POST на `/accounts/users/<id>/update/` (`accounts:user_update`) с `first_name`, `last_name`, `role`, заголовком `X-Requested-With: XMLHttpRequest` и `X-CSRFToken` из cookie.
- На `ok: true` — закрыть модалку, обновить в строке:
  - `.lk-team-name` — новый ФИО;
  - `.lk-avatar` — новые инициалы;
  - `.lk-team-info` — пересобрать строку: `{email} · {role_display.toLowerCase()} · {status_word}` (статус не меняем);
  - `data-role` на `.lk-team-row` и на kebab-пункте;
  - тост «Пользователь обновлён».
- На `ok: false` — показать ошибки в `lk-form-errors-summary` и под полями, **не** закрывать.

---

## 5. Правки в `accounts/views.py` и `accounts/tests.py`

- `AccountUserUpdateView` уже принимает `first_name` + `last_name` + `role` в одном POST. Изменения не нужны.
- Контекст `AccountCabinetView.get_context_data` **уже** содержит `user_limit`, `user_count_current`, `can_invite`, `last_activity` на `users_in_account`. Добавлять **не нужно ничего**. `overage_per_user` в контекст не добавляем (см. §1 про футер).
- `users_in_account` оставляем с `.exclude(user=request.user)` — self-row рендерим отдельным блоком в шаблоне перед `{% for %}` в том же `.lk-team-list`.
- В `accounts/tests.py` — добавить тест: админ POST'ом на `user_update` обновляет `first_name` + `role` одновременно и получает `ok:true` с обновлёнными значениями в ответе.
- Тесты v1.0 на instant-save (если были) — удалить.

---

## 6. Регрессия kebab/модалка

Версия 1.1 страдала от двух связанных багов:
1. **Kebab висит над модалкой.** Лечится `closeAllKebabs()` в начале `openModal()`.
2. **Кнопка «Сбросить пароль» срабатывает один раз.** Лечится сбросом `disabled` в `closeModal()` через `data-submit-default-label`.

После выпиливания инлайн-селекта роли (в §4 «Удалить») JS-поверхность уменьшается на ~50 строк, что само по себе снижает шанс таких регрессий.

**Обязательно:** прогнать Playwright-скрипт `scripts/cabinet_smoke.mjs`:
- (a) открыть kebab на чужой строке → «Редактировать…» → поменять ФИО и роль → «Сохранить» → в мета-строке появилась новая роль;
- (b) второй раз открыть kebab у **той же** строки → «Сбросить пароль» → confirm → success → модалка с паролем отображается.

---

## 7. Порядок работ

1. Удалить из `cabinet.html` self-card, чип «это вы», `.lk-self-footnote`, колонку статуса, `.lk-role-wrap`, подзаголовок «Сотрудники», старый подстрочник про сброс пароля.
2. Отрисовать self-row как первую строку `.lk-team-list` (40×40 аватар, жирный ФИО + `lk-role-chip--owner`, мета с последним входом, kebab с двумя пунктами «Редактировать профиль…» + «Сменить пароль»).
3. Отрисовать team-rows одной мета-строкой `{email · роль · статус}` со спан-обёрткой для не-активных состояний (`lk-meta-warn`, `lk-meta-off`).
4. Отрисовать футер — одно предложение про квоту/тариф/overage.
5. В `cabinet_modals.html` переименовать `edit-name-modal` → `edit-user-modal`, добавить `<select name="role">`.
6. В `cabinet.js` удалить `initInstantRoleSave`, опцию `undo` в `showToast`. Добавить `closeAllKebabs()` вызов в `openModal`, сброс `disabled` в `closeModal`, новый `initEditUserFlow`. Убедиться, что kebab-toggle работает одинаково и для self-row, и для team-row (селектор `[data-kebab-toggle]` не привязан к роли строки).
7. В `cabinet.css` выпилить `.lk-self-*`, `.lk-role-cell`, `.lk-role-select`, `.lk-role-pill`, `.lk-team-head`, `.lk-team-status`-как-колонку. Добавить `.lk-meta-warn`, `.lk-meta-off`, `.is-self`-правила, `text-decoration:none; color:inherit` в `.lk-kebab-item` (для пункта-ссылки «Сменить пароль»).
8. Тесты `accounts` + `tests.test_tenant_isolation`.
9. Playwright-smoke с двумя сценариями из §6 + дополнительно: открыть self-kebab → «Редактировать профиль…» → открывается `#edit-self-modal`; закрыть; открыть self-kebab снова → «Сменить пароль» → происходит навигация на `/accounts/password_change/`.

Итерационно. Если какой-то пункт требует правки `views.py`/`services.py`/`urls.py` сверх контекста + отсутствующих констант — остановиться и доложить.
