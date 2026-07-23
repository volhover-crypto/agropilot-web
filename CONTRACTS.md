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

## 11. E — Справочник пользователей / компетенции / права · v3.1 · Этап-2

Расширяет существующий задел М9 (таблица `team`). Отдельная таблица `users` НЕ вводится — team-member = user (ТЗ §5.1: «опирается на задел М9»; Non-goals: без лишних сущностей).

### 11.1 Таблица (расширение `team`)
- `competencies` JSONB DEFAULT '[]' — зоны/ниши (маршрутизация D-5 по совпадению).
- `permissions` JSONB DEFAULT '[]' — данные для будущего полного RBAC (DoD E п.3).
- `status` TEXT DEFAULT 'active' — active|inactive (D-5: неактивный → маршрут по компетенции).
- `role_key` TEXT NULL — нормализованная роль (admin|manager|smm|engineer). Существующий `role` НЕ трогаем (на него завязан фронт isManager()).

### 11.2 Эндпоинты
- `GET /v1/team`, `GET /v1/team/{id}` — любой авторизованный; `to_dict()` += competencies/permissions/status/role_key.
- `PATCH /v1/team/{id}` (competencies|permissions|status|role_key) — isManager() (enforcement по конвенции проекта; permissions[] пока данные, не gate).

### 11.3 Миграция / seed
- `backend/migrations/004_team_rbac.sql`: ALTER TABLE team ADD COLUMN (4 колонки с DEFAULT — seed U1–U5 и /v1/team не ломаются); UPDATE role_key: U1,U2→manager · U3,U5→engineer · U4→smm.

### 11.4 DoD Блока E
1. `/v1/team` отдаёт competencies/permissions/status/role_key (конверт {ok,data}).
2. Автор задания (added_by) — зависимость Шага 4 (Блок D), не в scope E.
3. Enforcement через isManager() (полный permissions[]-RBAC — позже, §7).

Scope-заметка: фронт isManager() (строковая роль 'Руководитель продаж') на Шаге 2 НЕ трогаем — перевод на role_key/permissions вынесен в Шаг 5 (Блок A, раздел team).

Флаг: USERS_READY: false


## 12. C — Стратегические задачи / сквозной контекст · v1 · Этап-2

Основание: `docs/TZ_STAGE2.md §5.2`, §5.4/A-1 и §7/Шаг 3.

`strategy_task` — самостоятельная стратегическая сущность для фокуса мониторинга и контекста ПЕТРУШКИ. Существующая `tasks` остаётся операционной сущностью и не расширяется полями Блока C.

Расширенная карточка из Приложения A (`backlog v2, не для MVP`) в текущий Блок C не входит.

### 12.1 Таблица `strategy_tasks`

Боевая схема: `public`.

- `id` VARCHAR(64) PRIMARY KEY.
- `title` TEXT NOT NULL.
- `description` TEXT NULL.
- `priority` VARCHAR(16) NOT NULL DEFAULT 'medium' — `low|medium|high`.
- `status` VARCHAR(16) NOT NULL DEFAULT 'active' — `active|inactive`.
- `monitoring_focus` JSONB NOT NULL DEFAULT '[]' — массив ключевых слов, ниш и рынков.
- `owner_id` VARCHAR(16) NOT NULL — ответственный пользователь.
- `added_by` VARCHAR(16) NOT NULL — автор создания.
- `linked_scenario` VARCHAR(64) NULL — ID сценария из `strategy.scenarios`.
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now().
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now().

`owner_id` и `added_by` логически ссылаются на `team.id`.

Для `linked_scenario` DB-FK не создаётся: сценарии находятся внутри JSONB-массива `strategy.scenarios`.

Неизвестные значения `priority` или `status` возвращают `VALIDATION_ERROR`.

### 12.2 API

Базовый путь:

`/agropilot/api/v1/strategy/tasks`

Эндпоинты:

- `GET /strategy/tasks` — список; любой авторизованный пользователь.
- `GET /strategy/tasks/{task_id}` — одна задача; любой авторизованный пользователь.
- `POST /strategy/tasks` — создание; manager/admin.
- `PATCH /strategy/tasks/{task_id}` — частичное изменение; manager/admin.
- `DELETE /strategy/tasks/{task_id}` — удаление; manager/admin.

Фильтры списка:

- `status`;
- `owner_id`;
- `linked_scenario`.

Сортировка:

1. `active`, затем `inactive`;
2. внутри статуса: `high`, `medium`, `low`;
3. затем `created_at DESC`.

Успешный ответ использует конверт:

`{"ok": true, "data": ...}`

Ошибки используют общий контракт проекта:

- `404 NOT_FOUND`;
- `403 FORBIDDEN`;
- `422 VALIDATION_ERROR`.

### 12.3 Payload

POST:

- обязательны `title`, `owner_id`;
- необязательны `description`, `priority`, `status`, `monitoring_focus`, `linked_scenario`;
- `added_by` backend получает из `get_current_user`;
- клиент не может передать или изменить `added_by`.

PATCH:

- разрешены `title`, `description`, `priority`, `status`, `monitoring_focus`, `owner_id`, `linked_scenario`;
- `id`, `added_by`, `created_at` неизменяемы;
- пустой PATCH возвращает `VALIDATION_ERROR`.

Backend валидирует:

- `title` после trim не пуст;
- `owner_id` существует в `team`;
- пользователь `owner_id` имеет `status='active'`;
- каждый элемент `monitoring_focus` — непустая строка;
- `linked_scenario`, если указан, существует в `strategy.scenarios`;
- `priority` и `status` входят в допустимые множества.

### 12.4 Права

Чтение доступно любому авторизованному пользователю.

POST/PATCH/DELETE разрешены, если `role_key` текущего пользователя входит в `manager|admin`.

Полный `permissions[]`-RBAC не входит в scope Блока C.

## 12.5 Frontend-интеграция

Frontend использует отдельную коллекцию `M.strategyTasks`; существующий одиночный объект `M.strategy` и его `GET/PUT /v1/strategy` не заменяются и не смешиваются со стратегическими задачами.

В `js/mock.objects.js` пустая и mock-модели получают `strategyTasks: []`. В `js/api.js` добавляются feature flag `STRATEGY_TASKS_READY` и методы `loadStrategyTasks()`, `createStrategyTask(data)`, `updateStrategyTask(id, data)`, `deleteStrategyTask(id)` для `/v1/strategy/tasks`.

`app.objects.js::_loadAllData()` загружает стратегические задачи вместе с остальными BFF-данными. Результат должен быть учтён во всех связанных местах: `Promise.all`, destructuring, проверке `allEmpty`, `apiData` и присвоении `this.M.strategyTasks`. Ошибка загрузки не должна незаметно подменять production-данные mock-снимком.

Текущий legacy-код `directions[]` не является моделью `strategy_task` и не расширяется в рамках Блока C.

## 12.6 Контекст ПЕТРУШКИ

`owlContext()` дополняется полем `strategyTasks`, содержащим только задачи со `status='active'`. Для каждой задачи в контекст передаются как минимум `id`, `title`, `owner_id`, `monitoring_focus`, `linked_scenario`, `priority` и `status`.

`monitoring_focus` используется ПЕТРУШКОЙ как набор фокусов мониторинга. Неактивные задачи в рабочий контекст не попадают. Отсутствие активных стратегических задач возвращает пустой массив и не нарушает существующий route/object-контекст.

## 12.7 Границы MVP

В scope Блока C входят: таблица и ORM-модель `strategy_tasks`, миграция, CRUD API, валидация, RBAC manager/admin на запись, frontend-загрузка в `M.strategyTasks` и инжект активных задач в `owlContext()`.

Вне scope: замена операционных `tasks`, переработка существующего `strategy_main`, расширенная карточка из Приложения A, новый lifecycle сверх `active|inactive`, автоматическое создание целей или операционных задач, а также рефакторинг legacy `directions[]`.

## 12.8 Definition of Done

Блок C принят, если одновременно выполнено следующее:

1. Миграция создаёт `strategy_tasks` по §12.1 и проходит на PostgreSQL без изменения существующей таблицы `strategy`.
2. Backend предоставляет согласованный CRUD `/v1/strategy/tasks` в конверте `{ok,data}`, использует `AsyncSession`, `Depends(get_db, get_current_user)` и зарегистрирован под `/agropilot/api/v1`.
3. Валидация и RBAC соответствуют §12.3–12.4; чтение доступно авторизованному пользователю, запись — только manager/admin.
4. Frontend загружает данные через `AGL.loadStrategyTasks()` в `M.strategyTasks` и не подменяет их `M.tasks` или `M.strategy`.
5. `owlContext()` получает только active-задачи и их `monitoring_focus`; inactive-задачи исключены.
6. Тесты покрывают CRUD, 401/403, 404, validation errors, фильтрацию active/inactive и frontend smoke-путь загрузки.
7. Проверены `git diff --check`, импорт приложения, регистрация router и raw HTTP-ответы; существующие `/v1/strategy` и route/object-контекст не регрессировали.

*Конец CONTRACTS.md*

## 13. D — ПЕТРУШКА: реестр источников /v1/sources + proposed на «Мой день» · Этап-2

Расширяет существующую таблицу `sources` (миграция 005, на проде пустая — 0 строк, подтверждено psql 2026-07-23). Блок E-min (team.competencies) выполнен (011, SHA 43817f2). owlContext strategyTasks-инжект уже есть (Блок C, §12.6).

### 13.1 Таблица (ревизия `sources`, вариант 1a)
Тип `type` приводится к TZ-набору (замена CHECK; таблица пуста → без миграции данных). Существующий канал `site/rss/telegram/tender` не используется фронтом и заменяется.

- `id` SERIAL PK — без изменений.
- `type` VARCHAR(16) NOT NULL CHECK IN ('news','supplier','competitor','market','tech') — ЗАМЕНА набора.
- `url` VARCHAR(500) NOT NULL — без изменений.
- `handle` VARCHAR(200) NULL — без изменений.
- `keywords` JSONB NOT NULL DEFAULT '[]' — без изменений (фильтрация).
- `active` BOOLEAN NOT NULL DEFAULT true — сохраняется (легаси-совместимость чтения); НЕ путать со `status`.
- `status` VARCHAR(16) NOT NULL DEFAULT 'active' CHECK IN ('active','proposed','disabled','rejected') — НОВОЕ (lifecycle D-6).
- `linked_strategy_task` VARCHAR(64) NULL — НОВОЕ, FK → strategy_tasks(id) ТОЛЬКО в миграции (локальный Base без ORM-FK, протокол 4 дефектов).
- `added_by` VARCHAR(16) NULL — НОВОЕ, FK → team(id) в миграции; автор задания (D-5.1).
- `receiver_user_id` VARCHAR(16) NULL — НОВОЕ, FK → team(id) в миграции; кому доставлено сейчас (D-5 служебное).
- `routing_reason` VARCHAR(16) NULL CHECK IN ('added_by','competency') — НОВОЕ, причина маршрутизации (D-5 служебное).
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now() — без изменений.

### 13.2 Эндпоинты /v1/sources (конверт {ok,data}; ошибки {ok:false,error:{code,message}})
- GET /v1/sources?status=&active=&limit= — любой авторизованный; фильтры опциональны.
- POST /v1/sources — создание. Роль manager/admin ИЛИ ПЕТРУШКА (proposed). added_by = get_current_user (клиент не задаёт).
- PATCH /v1/sources/{id} — правка полей type|url|handle|keywords|status|linked_strategy_task; id/added_by/created_at неизменяемы.
- POST /v1/sources/{id}/approve — только receiver (адресат D-5); переводит status='proposed'→'active'.
- POST /v1/sources/{id}/reject — только receiver; status→'rejected'.
- DELETE /v1/sources/{id} — manager/admin (soft: status='disabled').
Enforcement: role_key ∈ {manager,admin} через _is_manager() (эталон team/routes.py); адресность approve/reject — по receiver_user_id == user.id. Полный permissions[]-RBAC — вне scope (Stage-3 JWT).

### 13.3 Валидация (ValidationError → 422 VALIDATION_ERROR)
- `type` ∈ набора 13.1; `url` после trim не пуст; каждый keyword — непустая строка.
- `status` ∈ набора 13.1; `linked_strategy_task`, если задан, существует в strategy_tasks; `added_by`/`receiver_user_id`, если заданы, существуют в team и status='active'.
- POST от ПЕТРУШКИ обязан ставить status='proposed'; approve/reject на не-proposed → 409 CONFLICT.

### 13.4 Маршрутизация proposed (D-5, зафиксировано ТЗ §5.3)
При создании источника со status='proposed':
1. Если added_by задан и его team.status='active' → receiver_user_id=added_by, routing_reason='added_by'.
2. Иначе → по компетенции: пользователи team с status='active' и непустым пересечением competencies[] с keywords[]/linked_strategy_task.monitoring_focus → receiver_user_id первого подходящего, routing_reason='competency'.
3. Fallback «некуда» → тоже по компетенции (п.2). Если совпадений нет — receiver_user_id=NULL (в UI не доставлено, требует ручного назначения).
Approve/Reject доступны ТОЛЬКО пользователю receiver_user_id (не всей роли).

### 13.5 Контекст ПЕТРУШКИ (owlContext) — закрытие gap D-1
owlContext() дополняется:
- `activeSources` — источники со status='active', нормализованы до {id,type,url,keywords,linked_strategy_task,status}.
- `strategy` — заголовок/сценарий из M.strategy (закрытие G-2 gap-отчёта D-1).
Оба поля подмешиваются во ВСЕ 6 веток (all + goal/project/client/deal/task) тем же паттерном withST(), что и strategyTasks. Пустые массивы не ломают route/object-контекст. owlContextDealIds() не трогается.

### 13.6 Frontend-интеграция
- js/api.js: флаг SOURCES_READY:true; методы loadSources(), createSource(data), updateSource(id,data), approveSource(id), rejectSource(id) для /v1/sources.
- app.objects.js::_loadAllData(): loadSources() в Promise.all, destructuring, allEmpty, apiData, this.M.sources — БЕЗ подмены production mock-снимком (протокол Блока C).
- js/mock.objects.js: пустая и mock-модели получают sources:[].
- Легаси-UI (строки ~3504–3576) переводится с локального push({id:'SRC'...}) на createSource() BFF; локальная мутация srcToggle → PATCH status.

### 13.7 UI «Мой день»
Виджет «Предложения на мониторинг (N)» = источники status='proposed' с receiver_user_id == текущий пользователь; действия Одобрить/Отклонить (approve/reject). Одобренный → status='active' и попадает в owlContext активных источников; отклонённый → 'rejected'. Виджет рендерится в js/app.objects.js::vMyDay4() как отдельная зона.

### 13.8 Границы scope
В scope: ревизия sources (1a), CRUD+approve/reject, маршрутизация D-5, owlContext activeSources+strategy, frontend M.sources+SOURCES_READY, виджет «Мой день».
Вне scope: реальные внешние скрейперы (mock-слой сигналов), cron/авто-рекомендации (v2), лента мониторинга «по какому источнику» (DoD D п.5 — под-шаг Блока A-3), полный permissions[]-RBAC.

### 13.9 Definition of Done (по ТЗ §5.3)
1. owlContext() включает route/объект + strategy + активные strategyTasks + активные sources.
2. /v1/sources поддерживает типы news/supplier/competitor/market/tech и роль-автора (added_by).
3. ПЕТРУШКА может создать источник со status='proposed'.
4. proposed попадает в «Мой день» правильного пользователя по D-5; approve/reject доступны только receiver.
5. Миграция проходит на PostgreSQL без потери существующих строк (таблица пуста); git diff --check=0; router зарегистрирован; /v1/strategy, strategy_tasks и route/object-контекст без регрессий.

Флаг: SOURCES_READY: false → true (проставляется на Шаге frontend).
