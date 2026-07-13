# CONTRACTS — AgroPILOT / A PILOT
## API-контракт для вех M7 (Календарь), M9 (Версии/Навыки) и M4 (Стратегия)
Дата: 2026-07-10 | Обновлено: 2026-07-12 | Статус: СОГЛАСОВАН | Репозиторий: volhover-crypto/agropilot-web

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

### Формат ошибок (Error Contract)

Все ошибки **обязаны** возвращаться в едином формате:

```json
{
  "ok": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Event not found"
  }
}
```

**Стандартные коды ошибок:**

| Код | HTTP | Описание |
|------|------|-----------|
| `NOT_FOUND` | 404 | Ресурс не найден |
| `FORBIDDEN` | 403 | Нет прав (не владелец) |
| `UNAUTHORIZED` | 401 | Не аутентифицирован |
| `CONFLICT` | 409 | Конфликт состояния / дубликат |
| `VALIDATION_ERROR` | 422 | Ошибка валидации полей |
| `BAD_REQUEST` | 400 | Некорректный запрос |
| `INTERNAL_ERROR` | 500 | Внутренняя ошибка сервера |

> **Обязательное правило:** Все backend-модули (M7 Calendar, M9 Versions/Skills
> и все будущие роутеры) **обязаны** использовать классы из
> `backend/common/errors.py` (`NotFoundError`, `ForbiddenError`, `UnauthorizedError` и т.д.)
> вместо `raise HTTPException(...)` напрямую.
> Обработчики регистрируются **один раз** в `backend/main.py` через
> `register_error_handlers(app)` и действуют глобально для всего приложения.

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
  > **Реализация (routes.py):** `start = now.replace(day=1) - 7d`, `end = now.replace(day=28) + 7d` — приближённо, не точные границы месяца. При отладке помни об этом.

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

**Порог B→A (метрика зрелости навыка).**
> Предварительные пороговые значения, подлежат калибровке на реальных данных.

Формализация принципа ROADMAP.md «стабильно высокий объём+качество в режимах CONFIRM/AUTO → выделять отдельного фамильяра». Считается на клиенте по данным за фиксированное окно последние 30 дней (без скользящего пересчёта на этом этапе).

Источник данных — существующие сущности (новая сущность НЕ вводится): действия ПЕТРУШКА/оператора с градацией CONFIRM/AUTO (owlSuggestions и задачи с grade).

- Объём (V): число действий в режимах CONFIRM или AUTO за последние 30 дней. Условие: V >= 10.
- Качество (Q): доля принятых без правок (grade CONFIRM) от объёма V. Условие: Q >= 0.80 (80%).
- Порог достигнут ⇔ обе оси выполнены одновременно в пределах окна 30 дней: V >= 10 AND Q >= 0.80.

При V < 10 порог считается недостигнутым независимо от Q (недостаточно данных). Значение выводится на UI (#/skills) как индикатор «B→A: достигнут / не достигнут» с показом V и Q.

---

## 4. M4 — Стратегия-сценарии (Strategy)

### 4.1 Модель `strategy`

```json
{
  "id": "strategy_main",
  "title": "string",
  "horizon": "string (год/квартал)",
  "scenarios": [
    {
      "id": "SC1",
      "title": "string",
      "description": "string",
      "indicators": [
        { "id": "IND1", "text": "string", "status": "green|yellow|red" }
      ],
      "action_lines": [
        { "id": "AL1", "text": "string" }
      ]
    }
  ],
  "updated_at": "ISO-8601 datetime",
  "updated_by": "string (user_name из JWT)"
}
```

Ограничения: от 2 до 4 сценариев. Каждый сценарий: 1–10 индикаторов, 1–10 линий действий.

### 4.2 Эндпоинты M4

#### `GET /v1/strategy`
- Auth: required
- Response `data`: объект `Strategy` (один глобальный объект системы)
- Если ещё не создан — вернуть пустой шаблон с `scenarios: []`

#### `PUT /v1/strategy`
- Auth: required; `403` если не `isManager()` (role = manager|admin)
- Body: полный объект `Strategy` (заменяет целиком)
- `updated_at` и `updated_by` заполняются автоматически на backend
- Response `200`: `data: Strategy`

### 4.3 Флаг готовности

В `js/api.js` добавить:
```js
STRATEGY_READY: false,  // true -> AGL.loadStrategy() активно
```
Активировать только после подъёма `/v1/strategy` на реальном стенде.

### 4.4 Права доступа

| Действие | Условие |
|---|---|
| Читать стратегию | Любой авторизованный |
| Редактировать стратегию | role = manager или admin (`isManager()`) |

### 4.5 Интеграция с ПЕТРУШКОЙ

Стратегия = системный промпт ПЕТРУШКИ. После загрузки `owlContext()` обязан включать поле `strategy` с активными сценариями и индикаторами со статусом `yellow|red`.

---

## 5. Правила авторизации (сводка)

| Действие | Условие |
|---|---|
| Читать calendar events | Только свои (owner_id = current_user) |
| Создавать/изменять/удалять event | owner_id = current_user; `403` иначе |
| Читать deal versions | Любой авторизованный |
| Создавать/восстанавливать версию | Любой авторизованный |
| Читать навыки | Любой авторизованный |
| Изменять/удалить навык | user_id = current_user или role=admin |
| Читать стратегию | Любой авторизованный |
| Редактировать стратегию | role = manager или admin (`isManager()`) |

> **Примечание:** admin-условие временно не реализовано — ожидает системы ролей (RBAC); DELETE/PUT /team/skills защищены только по `user_id == current_user`. См. TODO-комментарий в `backend/versions/skills_router.py`.

---

## 6. Флаги готовности backend (фронтенд)

В `js/api.js` добавляются флаги (выставляет серверный агент после деплоя):
```js
CALENDAR_READY:  false,  // true -> AGL.loadCalendar() активно
VERSIONS_READY:  false,  // true -> AGL.loadVersions() активно
SKILLS_READY:    false,  // true -> AGL.loadSkills() активно
STRATEGY_READY:  false,  // true -> AGL.loadStrategy() активно
SOURCES_READY:   false,  // true -> AGL.loadSources() активно (Этап-2, M10)
KNOWLEDGE_READY: false,  // true -> AGL.knowledgeQuery() активно (Этап-2, M11)
UX_READY:        false,  // true -> AGL.loadInsights()/loadAgentQuestions() активно (Этап-2, M12)
```
В `app.objects.js` вызовы обёрнуты в `if (window.AGL.CALENDAR_READY) { ... }`.
При `DEV_MOCK=false` + флаг=false ни один запрос не уходит на backend, кнопки/секции не рендерятся.

---

## 7. Структура файлов backend

```
backend/
  README.md                    # Точка подключения для серверного агента
  calendar/
      models.py                # SQLAlchemy ORM модель CalendarEvent
      routes.py                # FastAPI router /v1/calendar
      migrations/
          001_create_calendar_events.sql
  versions/                    # ОДИН модуль для M9 (Versions + Skills)
      models.py                # ORM модели DealVersion + TeamSkill
      deals_versions_router.py # FastAPI router /v1/deals/:id/versions
      skills_router.py         # FastAPI router /v1/team/skills
      migrations/
          001_create_deal_versions.sql
          002_create_team_skills.sql
  strategy/                    # M4 — будущий модуль
      models.py                # ORM модель Strategy
      routes.py                # FastAPI router /v1/strategy
      migrations/
          001_create_strategy.sql
  main.py                      # Единая точка входа FastAPI; регистрирует роутеры
```


## 8. M10 — Реестр источников (Sources) · v3.1 · Этап-2

### 8.1 Таблица `sources`
| Поле | Тип | Описание |
|---|---|---|
| id | UUID PK | |
| title | TEXT | название источника |
| kind | TEXT | rss \| api \| web \| kb |
| url | TEXT | адрес/точка подключения |
| scope | JSONB | блоки ЖЦ, которые обслуживает (1..4) |
| trust | INT | 1..3, уровень доверия |
| status | TEXT | proposed \| pending \| verified \| revoked |
| verified_by / verified_at | TEXT / TIMESTAMPTZ | аудит верификации |
| scenario_id | TEXT NULL | привязка к сценарию Стратегии |

### 8.2 Эндпоинты M10
- `GET /v1/sources` — любой авторизованный.
- `POST /v1/sources` — любой авторизованный; создаёт со status=proposed.
- `POST /v1/sources/:id/verify` — любой авторизованный (кворум = 1) → status=verified.
- `PATCH /v1/sources/:id` (trust, revoke) — только isManager().
Стартовые коннекторы: arXiv, КиберЛенинка, открытые ресурсы. Среды (сайты/Telegram/соцсети) — подключение через SMM-раздел (Блок 1).
Флаг: `SOURCES_READY: false`.

## 9. M11 — Базы знаний (Knowledge / RAG) · v3.1 · Этап-2

### 9.1 Таблица `knowledge_bases`
{id UUID, title TEXT, corpus_version INT, doc_count INT, indexed_at TIMESTAMPTZ, verified_by TEXT, status TEXT}
Хранилище векторного индекса: Qdrant. Версия корпуса фиксируется (принцип версий M9).

### 9.2 Эндпоинты M11
- `GET /v1/knowledge` — любой авторизованный; `POST /v1/knowledge` — isManager().
- `POST /v1/knowledge/:id/query` — любой авторизованный; RAG-запрос для orchChat; ответ ОБЯЗАН содержать citations[] (источник каждого утверждения).
Флаг: `KNOWLEDGE_READY: false`.

## 10. M12 — МХ-мониторинг (UX Signals / Insights / Agent Questions) · v3.1 · Этап-2

### 10.1 Таблицы
- `ux_signals` {id, ts, channel: portal|social|search|chat, metric, value, ref}
- `insights` {id, ts, kind: request|expectation|forecast|ux_issue, text, source_refs JSONB, related (deal|project|scenario), status: new|accepted|rejected, actor_name}
- `agent_questions` {id, ts, user_id, question, context_ref, status: asked|deferred|answered|expired, answered_at, answer_text, insight_id}

### 10.2 Эндпоинты M12
- `GET /v1/ux/insights` — любой авторизованный; `POST` — агент/пользователь; `PATCH /:id` (accept|reject) — isManager().
- `GET /v1/petrushka/questions` — свои: любой; все: isManager(). `POST` — агент (ПЕТРУШКА). `PATCH /:id` (answer|defer) — адресат вопроса.
Правило автономности: проактивные вопросы ПЕТРУШКИ — AUTO и ОБЯЗАТЕЛЬНЫ, каждый вопрос фиксируется в agent_questions; пользователь может ответить отложенно из лога. Принятие/отклонение insight — обучающий сигнал Q-метрики навыка (M9).
Флаг: `UX_READY: false`.

---

*Конец CONTRACTS.md*
