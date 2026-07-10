# CONTRACTS — AgroPILOT / A PILOT
## API-контракт для вех M7 (Календарь) и M9 (Версии/Навыки)
Дата: 2026-07-10 | Статус: СОГЛАСОВАН | Репозиторий: volhover-crypto/agropilot-web

> Стек BFF явно не зафиксирован в репозитории.
> Backend-код написан на Python + FastAPI + SQLAlchemy (async) + PostgreSQL.
> Серверный агент адаптирует стек при необходимости, не меняя контракт эндпоинтов.

---

## 0. Общие соглашения

**Base URL:** `/agropilot/api/v1`

**Авторизация:** `Authorization: Bearer <JWT>` во всех запросах кроме публичных.
Backend декодирует JWT → получает `sub` (ид пользователя) и `name`/`full_name`/`login` (имя).
Паттерн идентичен M8-a (`_decodeUser` в `js/api.js`).

**Формат успешного ответа:**
```json
{ "ok": true, "data": <payload> }
```

**Формат ошибки:**
```json
{ "ok": false, "error": { "code": "NOT_FOUND", "message": "..." } }
```

**HTTP-коды:** 200, 201, 204, 400, 401, 403, 404, 422.

**Пагинация:** `?limit=N&offset=M` (по умолчанию limit=100).

---

## 1. M7 — Календарь (Calendar Events)

### 1.1 Таблица `calendar_events`

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | UUID | авто | PK |
| `title` | string(255) | да | Заголовок |
| `description` | text | нет | Детали |
| `start_at` | ISO-8601 datetime | да | Начало (UTC) |
| `end_at` | ISO-8601 datetime | нет | Конец (UTC); null = однодневное |
| `all_day` | boolean | нет | default false |
| `deal_id` | string/UUID | нет | FK deals.id (опц.) |
| `owner_id` | string/UUID | авто | Из JWT sub |
| `owner_name` | string | авто | Денормализовано из JWT |
| `kind` | enum | нет | meeting/call/deadline/other; default other |
| `created_at` | datetime | авто | |
| `updated_at` | datetime | авто | |

### 1.2 Эндпоинты M7

#### `GET /v1/calendar`
- Query: `?from=YYYY-MM-DD&to=YYYY-MM-DD&limit=200`
- Auth: required
- Response `data`: `Array<CalendarEvent>` — события текущего пользователя за период
- Если `from`/`to` не указаны: текущий месяц +-7 дней

#### `POST /v1/calendar`
- Auth: required
- Body обязательные поля: `title`, `start_at`
- Body опциональные: `description`, `end_at`, `all_day`, `deal_id`, `kind`
- `owner_id` / `owner_name` заполняются автоматически из JWT
- Response `201`: `data: CalendarEvent`

#### `PATCH /v1/calendar/:id`
- Auth: required; `403` если `owner_id != current_user`
- Body: любое подмножество полей кроме `id`, `owner_id`, `created_at`
- Response `200`: `data: CalendarEvent`

#### `DELETE /v1/calendar/:id`
- Auth: required; `403` если `owner_id != current_user`
- Response `204` (no body)

### 1.3 Фронтенд объект `CalendarEvent`
```
{ id, title, description, start_at, end_at, all_day, deal_id, owner_id, owner_name, kind, created_at, updated_at }
```

---

## 2. M9 — Версии сделок (Deal Versions)

### 2.1 Таблица `deal_versions`

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | UUID | авто | PK |
| `deal_id` | string/UUID | да | FK deals.id |
| `version_num` | integer | авто | Автоинкремент per deal (1,2,3...) |
| `snapshot` | jsonb | да | Полный снапшот полей сделки |
| `comment` | text | нет | Комментарий автора |
| `author_id` | string/UUID | авто | Из JWT sub |
| `author_name` | string | авто | Денормализовано из JWT |
| `created_at` | datetime | авто | |

### 2.2 Эндпоинты — Версии

#### `GET /v1/deals/:deal_id/versions`
- Auth: required
- Response `data`: `Array<DealVersion>` (сортировка version_num DESC)

#### `POST /v1/deals/:deal_id/versions`
- Auth: required
- Body: `{ "comment": "..." }` (все поля опциональны)
- Backend автоматически делает снапшот текущего состояния deals/:deal_id
- `version_num` = MAX(version_num for deal_id) + 1
- Response `201`: `data: DealVersion`

#### `GET /v1/deals/:deal_id/versions/:version_num`
- Auth: required
- Response `200`: `data: DealVersion` (с полным snapshot)

#### `POST /v1/deals/:deal_id/versions/:version_num/restore`
- Auth: required
- Восстанавливает безопасные поля сделки из snapshot:
  `title`, `stage`, `amount`, `description`, `need_type`, `culture`, `region`
  - НЕ перезаписывает: `id`, `client_id`, `owner_id`, `created_at`
  - Автосоздаёт новую версию с comment = "Restored from v{N}"
  - Response `200`: `data: { deal: Deal, new_version: DealVersion }`

  ---

  ## 3. M9 — Навыки команды (Team Skills)

  ### 3.1 Таблица `team_skills`

  | Поле | Тип | Обязательно | Описание |
  |---|---|---|---|
  | `id` | UUID | авто | PK |
  | `user_id` | string/UUID | да | FK users.id |
  | `user_name` | string | авто | Денормализовано |
  | `skill` | string(100) | да | Название навыка |
  | `level` | integer | нет | 1-5; default 3 |
  | `note` | text | нет | |
  | `updated_at` | datetime | авто | |
  UNIQUE: (`user_id`, `skill`)

  ### 3.2 Эндпоинты — Навыки

  #### `GET /v1/team/skills`
  - Auth: required
  - Query: `?user_id=<id>` (опционально)
  - Response `data`: `Array<TeamSkill>`

  #### `PUT /v1/team/skills` (upsert)
  - Auth: required
  - Body: `{ "user_id": "u1", "skill": "...", "level": 4, "note": "..." }`
  - Если (user_id, skill) есть — обновляет; иначе создаёт
  - `403` если user_id != текущий пользователь AND не admin
  - Response `200`: `data: TeamSkill`

  #### `DELETE /v1/team/skills/:id`
  - Auth: required; `403` если не владелец и не admin
  - Response `204`

  ---

  ## 4. Правила авторизации (сводка)

  | Действие | Условие |
  |---|---|
  | Читать calendar events | Только свои (owner_id = current_user) |
  | Создавать/изменять/удалять event | owner_id = current_user; `403` иначе |
  | Читать deal versions | Любой авторизованный |
  | Создавать/восстанавливать версию | Любой авторизованный |
  | Читать навыки | Любой авторизованный |
  | Изменять/удалить навык | user_id = current_user или role=admin |

  ---

  ## 5. Флаги готовности backend (фронтенд)

  В `js/api.js` добавляются три флага (выставляет серверный агент после деплоя):
  ```js
  CALENDAR_READY: false,  // true -> AGL.loadCalendar() активно
  VERSIONS_READY: false,  // true -> AGL.loadVersions() активно
  SKILLS_READY:   false,  // true -> AGL.loadSkills() активно
  ```
  В `app.objects.js` вызовы обёрнуты в `if (window.AGL.CALENDAR_READY) { ... }`.
  При `DEV_MOCK=false` + флаг=false ни один запрос не уходит на backend, кнопки/секции не рендерятся.

  ---

  ## 6. Структура файлов backend

  ```
  backend/
    README.md                    # Точка подключения для серверного агента
      calendar/
          models.py                  # SQLAlchemy ORM модель CalendarEvent
              routes.py                  # FastAPI router /v1/calendar
                  migrations/
                        001_create_calendar_events.sql
                          versions/
                              models.py                  # ORM модель DealVersion
                                  routes.py                  # FastAPI router /v1/deals/.../versions
                                      migrations/
                                            001_create_deal_versions.sql
                                              skills/
                                                  models.py                  # ORM модель TeamSkill
                                                      routes.py                  # FastAPI router /v1/team/skills
                                                          migrations/
                                                                001_create_team_skills.sql
                                                                ```

                                                                ---

                                                                *Конец CONTRACTS.md*
                                                                