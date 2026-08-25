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

## 12.9 Вью-раздел «Стратегия» (frontend, Alpine SPA)

Файл:         js/app.objects.js
Точка врезки: диспетчер вью, ветка `route === 'strategy'` -> this.vStrategy();
              ДОБАВЛЯЕТСЯ после ветки 'settings' (стр. ~472), ДО финальной
              else-заглушки «Раздел не найден» (стр. ~473 / полный ~758).
Метод:        vStrategy() — новый, по паттерну соседних vXxx().

Источник данных (read-only, из уже готового §12.5):
  - this.M.strategyTasks — массив стратегических задач (наполнен в loadFromAPI,
    app.objects.js:117; флаг STRATEGY_TASKS_READY: true, api.js:327).
  - НИКАКИХ новых fetch: рендер только уже загруженного this.M.strategyTasks.

Рендер (минимальный, только просмотр — CRUD-UI отдельным шагом):
  - Заголовок раздела «Стратегия».
  - Список задач: title, priority, status, monitoring_focus[] (как теги).
  - Пустое состояние: «Стратегических задач пока нет».

Флаг готовности: STRATEGY_VIEW_READY (реестр флагов §12).

НЕ ТРОГАЕМ:
  - Диспетчерные ветки других разделов (451–472) — только вставка одной ветки.
  - else-заглушку (473/758) — остаётся fallback.
  - §12.5 data-слой (api.js CRUD, loadFromAPI, M.strategyTasks) — без изменений.
  - §12.6 «Контекст ПЕТРУШКИ» (owlContext) — НЕ трогать, номер занят.
  - Backend /v1/strategy/tasks — без изменений.

Приёмка: #/strategy рендерит список из M.strategyTasks (или пустое состояние),
         консоль без красных ошибок, node --check pass.

## 12.11 Мониторинг: рендер источников под реальную схему sources (Блок D)

Файл: js/app.objects.js, метод vMonitoring(), блок «источники» (this.M.sources.map).
Причина: вью читает старую mock-схему (value/scope/industry/last), которых нет в backend
sources.to_dict() (реально: id/type/url/handle/keywords/active/status). На реальных данных —
undefined и КРАСШ на s.last.slice(5) (TypeError по undefined).

Backend НЕ трогаем. Маппинг полей во вью (блок источников):
  s.value          -> s.url
  s.scope          -> убрать
  s.industry       -> s.keywords (теги-пилюли, join по keyword)
  s.last.slice(5)  -> УДАЛИТЬ (нет поля даты; иначе TypeError)
  добавить s.handle рядом с url при наличии
  active / type / id -> без изменений (совпадают с backend)
Защита: (this.M.sources || []) — пустой список не должен ронять вью.

Блок «сигналы» (this.M.signals) — mock, НЕ трогаем (нет backend /v1/signals).
Кнопки data-src-scan / data-src-toggle — оставить как есть (обработчики к backend — отдельный шаг).

Приёмка: раздел «Мониторинг» рендерит источники из реальных sources (url/handle/type/keywords/
статус активности) без TypeError; пустой список не роняет вью; node --check pass; консоль чистая.

## 12.12 Мониторинг: форма «+ Источник» пишет в backend sources (persist, active)

Файл: js/app.objects.js, метод srcAddModal().
Проблема: форма делала this.M.sources.push(...) (mock value/scope/industry) без POST →
источник пропадал после перезагрузки. Backend: createSource -> POST /v1/sources.
Backend требует: type ∈ {news,supplier,competitor,market,tech}, url (обязат.),
handle (опц.), keywords (list), status ∈ VALID_STATUS.

Изменения (srcAddModal):
  - Поля: Тип (select value=backend-ключ, подпись рус.), URL (обязат.), Handle (опц.),
    Ключевые слова (строка через запятую -> keywords[]).
  - Убраны value/scope/industry и this.M.sources.push(...).
  - onSubmit async: r = await createSource({type,url,handle,keywords,status:'active'});
    r.ok===false -> toast(err), return false; успех -> M.sources = await loadSources();
    render(); toast('Источник добавлен','ok').
  - added_by НЕ шлём с фронта — проставляет backend (текущий пользователь / маршрутизация D-5).

НЕ трогаем: vMonitoring §12.11, блок сигналов, кнопки scan/toggle, backend.
Приёмка: источник сохраняется (POST 200), виден, ОСТАЁТСЯ после Ctrl+Shift+R; пустой url ->
toast без падения; node --check pass; консоль чистая.

## 13.1 A-6 «Входящие клиенты» — /v1/clients (API поверх существующей таблицы)

ФАКТ (проверено 2026-07-26): таблица public.clients УЖЕ существует, 5 записей C1-C5,
создана вне backend/migrations (ранний seed_prod.sql). На неё завязан живой FK:
deals.client_id -> clients(id), 8 сделок ссылаются. Пересоздание ЗАПРЕЩЕНО.
Фактическая схема: id varchar(16) PK NOT NULL, name varchar(255) NOT NULL,
industry varchar(100), region varchar(100), need text[], health varchar(20),
deals_count integer.
Проблема: нет API-слоя. js/api.js loadClients() деривит клиентов из /v1/deals?limit=200,
игнорируя реальную таблицу. DoD Блока A п.2 требует /v1/clients.

Решение: роутер поверх СУЩЕСТВУЮЩЕЙ таблицы + идемпотентный ALTER (только ADD COLUMN).
CREATE TABLE / DROP / изменение типов и FK — ЗАПРЕЩЕНЫ.

Миграция 013_clients_api.sql (идемпотентная, только добавление):
  ALTER TABLE clients ADD COLUMN IF NOT EXISTS source     varchar(32);
  ALTER TABLE clients ADD COLUMN IF NOT EXISTS status     varchar(16) DEFAULT 'active';
  ALTER TABLE clients ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();
  UPDATE clients SET status='active'  WHERE status IS NULL;
  UPDATE clients SET source='manual'  WHERE source IS NULL;
  UPDATE clients SET health='green'   WHERE health IS NULL;
  -- deals_count НЕ трогаем: колонка остаётся (её пишет seed), но API её НЕ читает.

Backend (паттерн backend/packages; локальный Base, без ORM-ForeignKey, to_dict(),
импорты backend.common.deps / backend.common.errors):
  backend/clients/{__init__.py,models.py,routes.py}
  models.py: Client, __tablename__="clients", need = mapped_column(ARRAY(Text)),
             id String(16), name String(255), industry/region String(100),
             health String(20), source String(32), status String(16), created_at TIMESTAMPTZ.
             to_dict() отдаёт need или [], БЕЗ deals_count.
  routes.py: clients_router = APIRouter(prefix="/clients", tags=["clients"])
  Регистрация в backend/main.py: app.include_router(clients_router, prefix="/agropilot/api/v1")

Эндпоинты, контракт {"ok":true,"data":...}:
  GET   /clients        ?status=&health=&limit=100 -> order by created_at desc nulls last, id
                        каждый элемент + dealsCount (SELECT count(*) FROM deals по client_id,
                        одним агрегирующим запросом, НЕ из колонки deals_count)
  GET   /clients/{id}   -> карточка + dealsCount; нет -> NotFoundError
  POST  /clients        body: id(опц., иначе генерим C<N>), name(обяз.), region, industry,
                        need[], health, source, status
  PATCH /clients/{id}   частичное обновление
  VALID_HEALTH={green,yellow,red}; VALID_STATUS={active,inactive,archived};
  VALID_SOURCE={manual,signal,smm,petrushka}; невалидное -> 422, не 500.

Frontend (js/api.js): loadClients() БЫЛО дерив из /v1/deals?limit=200 ->
  СТАЛО safeLoad('/v1/clients?limit=100'); комментарий "(derived from deals)" ->
  "(implemented)". js/app.objects.js НЕ трогаем — он уже маппит
  {id,name,industry,region,need,health,dealsCount}.

Флаг: CLIENTS_READY = true (после restart + curl 200).
НЕ трогаем: deals, sources, RBAC, seed_prod.sql, колонку deals_count, FK.

Приёмка:
  [ ] \d clients: появились source/status/created_at; id/PK/FK не изменились
  [ ] SELECT count(*) FROM clients = 5 (данные целы)
  [ ] curl /v1/clients = {ok,data}, 5 клиентов, dealsCount из deals (C1..C5 суммарно 8)
  [ ] POST нового клиента -> 200, виден в GET
  [ ] невалидный health -> 422
  [ ] UI «Входящие клиенты» рендерит 5 клиентов после Ctrl+Shift+R, консоль чистая
  [ ] py_compile pass; node --check js/api.js pass

## 14. A-6.1 «Лиды» — /v1/leads + импорт базы Bitrix24

ПРИЧИНА: у клиента есть выгрузка Bitrix24 (contacts_bitrix24.csv, 1491 строка).
916 уникальных компаний. Из них 693 — недозвон/отказ/не ЦА, 223 перспективных.
Заливать это в clients НЕЛЬЗЯ: clients = реестр тех, с кем работают (5 записей,
живой FK от 8 сделок). Лид = стадия ДО клиента (§6 ТЗ: Сигнал -> может стать
клиентом). Поэтому отдельная сущность leads + явная конвертация лид->клиент.

НУМЕРАЦИЯ: номер 13.2 в этом файле УЖЕ ЗАНЯТ (13.2 Эндпоинты /v1/sources).
Данный контракт = §14. Не путать.

Миграция 014_leads.sql (новая таблица, FK на clients сразу):
  CREATE TABLE IF NOT EXISTS leads (
    id                  varchar(16) PRIMARY KEY,
    name                varchar(255) NOT NULL,
    status              varchar(16) NOT NULL DEFAULT 'new',
    contact_person      varchar(255),
    phone               varchar(32),
    phone_extra         text[],
    email               varchar(255),
    owner               varchar(64),
    region              varchar(100),
    industry            varchar(100),
    ext_id              varchar(32),
    comment             varchar(255),
    source              varchar(32) DEFAULT 'bitrix24',
    converted_client_id varchar(16),
    created_at          date,
    imported_at         timestamptz DEFAULT now(),
    CONSTRAINT leads_converted_client_id_fkey
      FOREIGN KEY (converted_client_id) REFERENCES clients(id) ON DELETE SET NULL
  );
  CREATE INDEX IF NOT EXISTS leads_status_idx ON leads(status);
  CREATE INDEX IF NOT EXISTS leads_ext_id_idx ON leads(ext_id);
FK создаётся В МИГРАЦИИ. В ORM-модели ForeignKey НЕТ (протокол 4 дефектов).
region/industry = NULL: в выгрузке Bitrix24 этих полей нет вообще.

Backend (паттерн backend/clients, эталон backend/packages):
  backend/leads/{__init__.py,models.py,routes.py}
  models.py: Lead, __tablename__="leads", локальный Base, phone_extra ARRAY(Text),
             created_at Date, imported_at TIMESTAMP(timezone=True),
             to_dict() -> camelCase: contactPerson, phoneExtra, extId,
             convertedClientId, createdAt, importedAt.
  routes.py: leads_router = APIRouter(prefix="/leads", tags=["leads"])
  main.py:   app.include_router(leads_router, prefix="/agropilot/api/v1")

Эндпоинты, конверт {"ok":true,"data":...}:
  GET  /leads   ?status=&owner=&q=&limit=50&offset=0
                ПАГИНАЦИЯ ОБЯЗАТЕЛЬНА (916 записей). limit по умолчанию 50, le=200.
                q = ILIKE по name/contact_person/phone.
                data = {"items":[...],"total":<int>,"limit":<int>,"offset":<int>}
                order by name.
  GET  /leads/{id}         -> объект; нет -> NotFoundError
  PATCH /leads/{id}        -> частичное обновление
  POST /leads/{id}/convert -> создаёт клиента в clients:
       id клиента = _next_id() (C6, C7...), name/region/industry из лида,
       health='green', source='bitrix24', status='active';
       затем лиду: status='converted', converted_client_id=<новый C-id>.
       Повторная конвертация -> 409. Возврат: {"lead":{...},"client":{...}}
  VALID_STATUS = {new, active, inactive, converted}
  Невалидный status -> 422 (не 500).

Импорт данных (ПОСЛЕ проверки API на пустой таблице):
  10 фрагментов по ~92 строки, INSERT ... ON CONFLICT (id) DO NOTHING.
  Идемпотентны, порядок не важен, повторный прогон безопасен.
  Ожидаемый итог: 916 строк, 223 active / 693 inactive, phone у 909.
  Телефоны восстановлены из Excel-нотации (+7.9780001738e+10 -> +79780001738,
  все 11 цифр сохранены); склейки по 22/33 цифры разрезаны по 11.
  В leads попадает 1266 номеров (1285 до дедупа внутри группы); 1788 в ранней
  редакции §14 — счёт по ВСЕМУ CSV, включая 553 строки без компании, которые
  в leads не импортируются. Невосстановимых токенов 9 (длины 13/15/17).

Frontend: новый раздел «Лиды» с пагинацией и фильтром по статусу.
  clients/deals/sources НЕ ТРОГАЕМ. Флаг LEADS_READY после curl 200.

НЕ трогаем: clients (кроме вставки строк при convert), deals, sources, RBAC,
seed_prod.sql, 013_clients_api.sql.

Приёмка:
  [ ] \d leads: таблица есть, FK leads_converted_client_id_fkey -> clients(id) ON DELETE SET NULL
  [ ] curl /v1/leads на ПУСТОЙ таблице = {ok,data:{items:[],total:0}}
  [ ] импорт 10 фрагментов -> SELECT count(*) = 916
  [ ] SELECT status,count(*) GROUP BY -> active 223, inactive 693
  [ ] SELECT count(*) WHERE phone IS NOT NULL = 909
  [ ] curl /v1/leads?limit=5 -> 5 items, total 916
  [ ] curl /v1/leads?q=агро -> непустой результат
  [ ] POST /leads/{id}/convert -> клиент создан, лид converted, clients 5->6
  [ ] невалидный status -> 422
  [ ] регресс: clients/deals/sources = 200
  [ ] UI раздел «Лиды» рендерит с пагинацией
  [ ] py_compile pass; node --check pass

## 15. A-6.1 UX v2 — раздел «Лиды» для менеджера по продажам

ПРИЧИНА: раздел (§14) технически работает, но непригоден для работы. По скрину
прода 2026-07-26: техн. ID B1..B916 в первой колонке, статус латиницей
(active/inactive) без цвета, ФИО с должностью и длинные названия не обрезаны —
строки ломаются на 2-3 линии, телефон не кликабелен, действий в строке нет
(POST /leads/{id}/convert реализован, но из UI недоступен), колонка «Клиент»
пуста у всех, комментарий (причина отказа) не выводится вообще, нет пагинации
внизу, счётчиков в табах, сортировки и фильтра по ответственному.

ОБРАЗЕЦ: Битрикс24 (список с настраиваемыми колонками, статус = цветная стадия,
карточка = статическая часть + история общения) и общая практика CRM-списков
(мало колонок без горизонтальной прокрутки, длинные тексты не выводить целиком,
статус цветом, действия в строке, пагинация ~50-100 строк).
Канбан и календарь — ВНЕ MVP.

### 15.1 P0 — минимум пригодности

Колонки ровно 7, в этом порядке:
  Название | Контакт | Телефон | Статус | Ответственный | Комментарий | Действия
Техн. id в таблице НЕ выводится (только в карточке §15.2).

  Название       — одна строка, CSS-обрезка (text-overflow:ellipsis), title=полное.
  Контакт        — только ФИО, обрезка одной строкой, title=полное. Должность —
                   в карточку, не в таблицу.
  Телефон        — ссылка <a href="tel:+7XXXXXXXXXX">. Если phone_extra непустой —
                   рядом значок «+N» с тултипом-перечнем.
  Статус         — цветной бейдж, подписи по-русски. Маппинг ТОЛЬКО в UI, значения
                   в БД не менять: new -> «Новый» (серый), active -> «В работе»
                   (зелёный), inactive -> «Отклонён» (приглушённый серый),
                   converted -> «Клиент» (синий).
  Ответственный  — как есть, обрезка.
  Комментарий    — одна строка с обрезкой, title=полное (это причина отказа).
  Действия       — «Позвонить» (tel:), «В клиенты», «Открыть».

Действие «В клиенты»: POST /v1/leads/{id}/convert, доступно только при
status IN (new, active), с подтверждением («Создать клиента из лида <name>?»).
После 200 строка обновляется на «Клиент» без перезагрузки раздела; счётчики
табов пересчитываются. 409 -> тост «Лид уже сконвертирован».

Пагинация внизу: «1-50 из 916», кнопки назад/вперёд, селектор 50/100.
Использовать total/limit/offset из §14 (data.total). Всю базу на фронт НЕ грузить.

Счётчики в табах: Все N · Новые N · В работе N · Отклонённые N · Клиенты N.
Один агрегатный запрос, НЕ подсчёт по текущей выборке:
  GET /v1/leads/stats -> {"ok":true,"data":{"total":916,"new":0,"active":223,
                          "inactive":693,"converted":0}}
  Реализация: SELECT status, count(*) FROM leads GROUP BY status.
  Роутинг: путь /leads/stats объявить ДО /leads/{id}, иначе «stats» уйдёт в {id}.

### 15.2 P1 — рабочий сценарий менеджера

- Фильтр «Ответственный» (select из фактических значений) + кнопка «Мои лиды»
  (по текущему пользователю). Главный сценарий: 916 лидов на 4 ответственных.
- Сортировка по клику на заголовок: Название, Статус, Ответственный.
  Параметр sort=name|status|owner и order=asc|desc в GET /leads (расширение §14,
  дефолт остаётся order by name asc).
- Карточка лида (модалка): слева статические данные (все поля, включая ext_id,
  все телефоны, email, дата создания), справа — зарезервированное место под
  историю касаний. Редактирование через существующий PATCH /leads/{id}.
- Поиск: debounce 300 мс (не запрос на каждый символ), подсветка совпадения.

### 15.3 Вне MVP (отдельные контракты, не смешивать с §15)

- Поля next_action (text) + next_action_at (date) + подсветка просроченных.
  Требует миграции — только отдельным контрактом.
- Экспорт отфильтрованного списка в CSV.
- Массовые действия (чекбоксы, смена ответственного).
- Канбан-вид по статусам, календарь.

### 15.4 Границы

- Схема leads НЕ меняется. Из API добавляется только GET /leads/stats и
  параметры sort/order у GET /leads.
- clients, deals, sources, strategy_tasks, RBAC — НЕ трогать.
- Правки фронта — только вью раздела «Лиды» и его методы в js/api.js.
- Флаг LEADS_READY остаётся; новых флагов не вводить.

### 15.5 Definition of Done

  [ ] curl /v1/leads/stats = {ok,data:{total:916,active:223,inactive:693,...}}
  [ ] /leads/stats не перехватывается /leads/{id} (проверка: 200, не NotFound)
  [ ] таблица = 7 колонок, техн. id отсутствует
  [ ] все строки одной высоты при 916 записях (нет переносов в 2-3 линии)
  [ ] телефон открывает tel:, «+N» показывает доп. номера
  [ ] бейджи статусов русскоязычные и цветные
  [ ] «В клиенты» на active-лиде: клиент создан, лид -> «Клиент», счётчики обновились
  [ ] повторный convert -> 409 + тост, без 500
  [ ] пагинация: «1-50 из 916», переход на стр. 2 меняет содержимое
  [ ] «Мои лиды» и фильтр по ответственному сужают выборку (P1)
  [ ] сортировка по 3 колонкам работает в обе стороны (P1)
  [ ] регресс: clients/deals/sources/strategy = 200, разделы рендерят
  [ ] py_compile pass; node --check pass

### 15.6 Механики лидов по Битрикс24 и уточнение объёма

ИСТОЧНИК: helpdesk.bitrix24.ru/open/23172742/ «Лиды: что это и как с ними
работать». Ниже — механики оттуда и решение по каждой для AgroPILOT.

1. ЛИД = ОБРАЩЕНИЕ, У ЛИДА ЕСТЬ ИСТОЧНИК. Битрикс делит лиды на простые и
   повторные; у повторного ВСЕГДА заполнено поле «Клиент» (обращение того, кто
   уже есть в базе).
   Решение: пустая колонка «Клиент» — не дефект, это признак повторного лида.
   Из таблицы она убрана (15.1); в карточке (15.2) выводить «Клиент: —» либо
   ссылку на C-клиента по converted_client_id. Поле source обязательно:
   у всех 916 импортированных = 'bitrix24'; для новых лидов — выбор из
   существующего реестра §13 /v1/sources. Новый справочник НЕ создавать.

2. СТАДИИ, А НЕ СТАТУСЫ: настраиваемые, цветные, с количеством лидов на каждой
   и с явным «какие лиды ещё не взяли в работу».
   Решение: наши new|active|inactive|converted = стадии. Фиксируем маппинг:
   new «Новый / не взят в работу», active «В работе», inactive «Некачественный»,
   converted «Сконвертирован». Стадия new — отдельный рабочий фильтр
   (контроль необработанных), а не просто ярлык. Счётчики — GET /leads/stats.

3. ЗАВЕРШЕНИЕ РАБОТЫ: два исхода, проходить все стадии необязательно.
   Качественный лид -> конвертация, причём в Битриксе лид конвертируется В СДЕЛКУ
   (с выбором создаваемого элемента). Некачественный -> стадия «Некачественный».
   Решение: расхождение с §14 (наш convert создаёт только клиента) устраняется
   в 15.7. Дополнительно нужно действие «Некачественный» из строки списка:
   PATCH status='inactive' + ОБЯЗАТЕЛЬНЫЙ комментарий-причина (пустой -> 422).
   Сейчас перевести лид в отказ из UI невозможно.

4. ДЕЛА (звонок/встреча с крайним сроком) — ядро ежедневной работы: «+ Дело»
   в карточке, отдельный режим просмотра раскладывает лиды по крайнему сроку.
   Решение: приоритет поднят из 15.3 в P1 в минимальном виде — поля
   next_action text, next_action_at date (ALTER TABLE ADD COLUMN, без FK),
   сортировка по next_action_at, подсветка просроченных. Полный режим «Дела»
   и история касаний остаются вне MVP.

5. РЕЖИМЫ ПРОСМОТРА: канбан / список / дела / календарь. Список — выбираемые
   колонки, фильтры, массовое редактирование. Канбан — смена стадии перетаскиванием.
   Решение: MVP = только список (подтверждает 15.1). Канбан обоснован именно как
   перетаскивание между стадиями — следующая итерация, отдельный контракт.

6. ПРАВА ДОСТУПА: сотрудник видит только свои лиды, руководитель — все.
   Решение: RBAC не трогаем. Кнопка «Мои лиды» (15.2) — ПОВЕДЕНЧЕСКИЙ эквивалент,
   UI-фильтр по ответственному, НЕ ограничение доступа. Не выдавать за RBAC.

7. СОЗДАНИЕ ЛИДА: вручную кнопкой «Создать», импорт, миграция, контакт-центр,
   CRM-формы. У нас реализован только импорт; кнопки «Создать лид» в UI нет,
   POST /leads в §14 не описан.
   Решение: создание вручную — P0 (см. 15.7). Контакт-центр и CRM-формы — вне
   объёма Этапа-2.

ИТОГ ПО ОБЪЁМУ §15 (инкремент к уже сделанному 15.1):
  P0 (+): кнопка «Создать лид» + POST /v1/leads; действие «Некачественный»
          с обязательным комментарием.
  P1 (+): next_action / next_action_at + подсветка просроченных; source в карточке.
  §14:    convert с опцией «клиент + сделка» (15.7).
  Вне MVP (без изменений): канбан, календарь, режим «Дела», история касаний,
          массовое редактирование, экспорт CSV, пользовательская настройка колонок.

### 15.7 ПРАВКА §14 — API-дополнения (перекрывает §14 в указанных точках)

A. POST /v1/leads — создание лида вручную (в §14 отсутствовал).
   Вход: name (обязателен), contact_person, phone, owner, source, comment,
         status (по умолчанию 'new').
   id генерируется как _next_id() по существующей схеме B<N> (после B916).
   Пустой name -> 422. Ответ: {"ok":true,"data":{...lead}}.

B. POST /v1/leads/{id}/convert — расширяется параметром target.
   target = "client" (по умолчанию, поведение §14 без изменений)
          | "client_deal" -> создаёт клиента КАК В §14, затем сделку в deals:
            id по _next_id() схемы deals, client_id = новый C-id,
            name = «Сделка по лиду <lead.name>», начальный статус — первый
            в существующем VALID_STATUS deals (не изобретать новый),
            сумма/дата не заполняются.
   Возврат: {"lead":{...},"client":{...},"deal":{...}|null}.
   Повторная конвертация -> 409 (без изменений).
   ЯВНО ПЕРЕКРЫВАЕТ строку §14 «НЕ трогаем: ... deals ...» — вставка строк
   в deals при target=client_deal разрешена. Схему deals НЕ менять.

C. PATCH /v1/leads/{id} — при переводе в status='inactive' поле comment
   обязательно и непустое, иначе 422.

D. GET /v1/leads — добавляются sort=name|status|owner|next_action_at и
   order=asc|desc (дефолт name asc), плюс фильтр owner=<строка>.

Definition of Done для 15.6/15.7: ВЫПОЛНЕН 2026-08-25 (реализация b80b2a4).
  [x] POST /leads: создан B917, виден в списке; пустой name -> 422
  [x] convert target=client -> как раньше; target=client_deal -> client + deal созданы
  [x] повторный convert -> 409, без 500
  [x] PATCH в inactive без comment -> 422; с comment -> 200
  [x] \d leads: next_action, next_action_at добавлены, без FK (P1)
  [x] sort/order/owner работают, дефолт не изменился
  [x] регресс: clients/deals/sources/strategy = 200, разделы рендерят
  [x] py_compile pass; node --check pass
### 15.1a P0 — читаемость таблицы «Лиды» (уточнение по итогам UI-приёмки 2026-07-26)

Обрезка текста в одну строку СОХРАНЯЕТСЯ (§15.1, DoD «строки одной высоты»).
Запрос Оркестратора на перенос строк отклонён как противоречащий причине §15.
Взамен читаемость обеспечивается границами и управляемой шириной колонок.

Границы:
- Видимая горизонтальная линия под каждой строкой (1px, var(--border)).
- Видимая вертикальная линия между колонками (1px, var(--border)).
- Подсветка строки при наведении (var(--surface-2)).
- Шапка таблицы залипающая (position: sticky, top: 0) при прокрутке списка.

Ресайз колонок:
- Ширина задаётся через <colgroup>; таблица table-layout: fixed.
- У правой границы каждого <th> — зона захвата 5px, курсор col-resize.
- Перетаскивание мышью меняет ширину колонки; минимум 60px, максимум 600px.
- Ширины сохраняются в localStorage под ключом 'agl_leads_colw' и
  восстанавливаются при следующем открытии раздела.
- Двойной клик по зоне захвата сбрасывает ширину колонки к значению по умолчанию.
- Ширины по умолчанию (px): Название 260, Контакт 180, Телефон 150, Статус 110,
  Ответственный 160, Комментарий 220, Действия 200.

Границы изменения:
- Правится только вью «Лиды» в js/app.objects.js и <style> в index.html.
- Общие стили таблиц других разделов НЕ трогать: селекторы скоупить под
  контейнер #leadsTable.
- Backend, схема БД, API — без изменений.

DoD 15.1a:
  [ ] у каждой строки видна нижняя граница, между колонками — вертикальные линии
  [ ] наведение подсвечивает строку целиком
  [ ] шапка не уезжает при прокрутке
  [ ] курсор col-resize у правого края заголовка; перетаскивание меняет ширину
  [ ] ширины переживают F5 (localStorage)
  [ ] двойной клик по зоне захвата возвращает ширину по умолчанию
  [ ] строки остаются одной высоты, обрезка и title сохранены
  [ ] таблицы разделов «Клиенты» и «Сделки» визуально не изменились


### 15.8 ПРАВКА §14 — «Дело» по лиду доступно на запись (достройка P1 из §15.6 п.4)

ПРИЧИНА. §15.6 п.4 поднял «Дела» в P1 и потребовал поля next_action /
next_action_at, сортировку по сроку и подсветку просроченных. §15.7 P1 описал
только миграцию, а §15.7 D — только сортировку. Список полей, принимаемых
PATCH /v1/leads/{id}, задан в §14 и этих полей не содержит; §15.7 C правит в
PATCH единственное правило — обязательный comment при inactive. В результате
после реализации §15.6/§15.7 (2026-08-25) поля читаются, сортируются и
подсвечиваются, но заполнить их из приложения нечем — только SQL-ом.
Это пробел контракта, а не реализации.

A. PATCH /v1/leads/{id} — к списку полей §14 добавляются:
     next_action     string|null  — что за дело (звонок, встреча, письмо)
     next_action_at  date|null    — крайний срок, строго ISO 'YYYY-MM-DD'
   Правила:
   - поля независимы: допустимо задать срок без текста и текст без срока;
   - явный null очищает поле (семантика exclude_unset §14 не меняется);
   - неразбираемая дата -> 422 (обрабатывается схемой, отдельный код не нужен);
   - правило §15.7 C (обязательный comment при переводе в inactive) не меняется
     и на эти поля не распространяется.
   Схема БД НЕ меняется: колонки уже созданы миграцией 015_leads_next_action.sql.

B. UI — действие «Дело» в строке лида, для статусов new|active.
   Модалка: текст дела + дата (input type=date). Пустая форма -> очистка полей.
   Отображение уже реализовано в §15.6 п.4: колонка «Дело до», сортировка
   sort=next_action_at, подсветка просроченных цветом var(--err).

C. ГРАНИЦЫ (подтверждают §15.6 п.4 и §15.3, ничего не расширяют).
   Вне MVP остаются: отдельный режим просмотра «Дела», история касаний,
   напоминания и уведомления, несколько дел на одном лиде. Здесь ровно одно
   ближайшее дело на лид, хранимое в двух колонках.

DoD 15.8: ВЫПОЛНЕН 2026-08-25 (реализация fa814c3).
  [x] PATCH с next_action + next_action_at -> 200, поля в ответе
  [x] PATCH с next_action_at='2026-13-45' -> 422, без 500
  [x] PATCH с null очищает оба поля
  [x] PATCH в inactive по-прежнему требует comment (§15.7 C не сломан)
  [x] sort=next_action_at раскладывает лиды по сроку
  [x] просроченный срок подсвечен в таблице, будущий — нет
  [x] регресс: clients/deals/sources/strategy = 200, разделы рендерят
  [x] py_compile pass; node --check pass
