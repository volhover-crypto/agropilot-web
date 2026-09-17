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
- ПРАВКА 2026-08-25: на момент написания §15.1a колонок было семь. §15.6 п.4
  добавил восьмую — «Дело до» (next_action_at). Её ширина по умолчанию 120px,
  она участвует в ресайзе и сохранении наравне с остальными. Ключи колонок в
  localStorage: name, contact, phone, status, owner, comment, next_action_at,
  actions.
- Обрезка в одну строку сохраняется, но фиксированный `max-w-[180px]` на ячейках
  снимается: при `table-layout: fixed` ширину задаёт <colgroup>, иначе ресайз
  колонки шире 180px не даёт видимого эффекта. Класс `truncate` остаётся.

Границы изменения:
- Правится только вью «Лиды» в js/app.objects.js и <style> в index.html.
- Общие стили таблиц других разделов НЕ трогать: селекторы скоупить под
  контейнер #leadsTable.
- Backend, схема БД, API — без изменений.

DoD 15.1a: ВЫПОЛНЕН 2026-08-25 (реализация d5321a6).
  [x] у каждой строки видна нижняя граница, между колонками — вертикальные линии
  [x] наведение подсвечивает строку целиком
  [x] шапка не уезжает при прокрутке
  [x] курсор col-resize у правого края заголовка; перетаскивание меняет ширину
  [x] ширины переживают F5 (localStorage)
  [x] двойной клик по зоне захвата возвращает ширину по умолчанию
  [x] строки остаются одной высоты, обрезка и title сохранены
  [x] таблицы разделов «Клиенты» и «Сделки» визуально не изменились
  [x] колонка «Дело до» ресайзится и сохраняется наравне с остальными


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


## 16. A-7 «Сделки» — словарь стадий и валидация stage в /v1/deals

ПРИЧИНА. `PATCH /v1/deals/{id}` принимает в `stage` ЛЮБУЮ строку: в
`backend/deals/routes.py` нет ни набора допустимых значений, ни проверки —
`setattr(deal, 'stage', <что угодно>)`. Опечатка в UI или скрипте молча создаёт
несуществующую стадию, после чего сделка выпадает из воронки (фронт группирует
по известным кодам) и из фильтра `GET /deals?stage=`. Это же отсутствие набора
вынудило §15.7 B ссылаться на «первый из существующего VALID_STATUS deals» —
сущность, которой в коде нет; при реализации 2026-08-25 значение пришлось брать
из `default` модели.

СЛОВАРЬ. Источник — `STAGE_MAP` в `js/app.objects.js:121`, единственное место в
проекте, где стадии определены. Новых кодов НЕ вводим, существующие НЕ
переименовываем:

    lead      Зацепка          assess     Оценка
    proposal  Договор          deal       Проектирование
    won       Реализация       lost       Проиграна
    service   Сервис           cancelled  Отменена

Порядок значим: первый элемент (`lead`) — стартовая стадия. В БД сейчас заняты
четыре кода (lead 4, assess 2, proposal 2, deal 1), все входят в словарь, то
есть валидация не ломает ни одной существующей строки.

A. `VALID_STAGES` объявляется в `backend/deals/models.py` — кортеж в порядке
   воронки. Отступление от стиля проекта (в leads `VALID_STATUS` лежит в
   routes.py) сделано осознанно: словарь нужен ДВУМ роутерам, а импорт одного
   роутера в другой хуже импорта из модели.

B. `PATCH /v1/deals/{id}` — `stage` вне словаря -> 422 VALIDATION_ERROR с
   перечнем допустимых. Допустимые значения работают как раньше. Поля `score`,
   `signal` не трогаются.

C. `GET /v1/deals?stage=<код>` — код вне словаря -> 422. Сейчас такой запрос
   молча отдаёт пустой список, что неотличимо от «сделок нет».

D. `backend/leads/routes.py`: константа `DEAL_INITIAL_STAGE` заменяется на
   `VALID_STAGES[0]`. Значение остаётся `lead` — поведение §15.7 B не меняется,
   уходит только дублирование. Комментарий про «набора нет» снимается.

E. Схема БД НЕ меняется. CHECK-констрейнт на `deals.stage` намеренно НЕ
   добавляем: в ту же БД пишут внешние процессы вне этого репозитория, и отказ
   на уровне БД уронил бы их вставки. Валидация — на уровне API.

F. ГРАНИЦЫ. Здесь только словарь и отказ на неизвестном коде. Вне scope:
   допустимость переходов между стадиями (какая из какой), права на смену
   стадии, канбан-перетаскивание, изменение набора стадий, приведение
   дублирующихся карт `REV` во фронте (js/app.objects.js:1781 и :1795).

DoD 16: ВЫПОЛНЕН 2026-08-25 (реализация 5984198).
  [x] PATCH /deals/{id} со stage=bogus -> 422, без 500
  [x] PATCH со всеми 8 кодами словаря -> 200
  [x] GET /deals?stage=bogus -> 422; ?stage=lead -> только сделки этой стадии
  [x] существующие 9 сделок не изменились
  [x] convert target=client_deal по-прежнему создаёт сделку со стадией lead
  [x] регресс: leads/clients/deals/sources/strategy = 200, разделы рендерят
  [x] py_compile pass


## 17. A-3 «Мониторинг» — лента наблюдений /v1/monitoring

ПРИЧИНА. A-3 — единственный раздел Блока A без backend-роутера (ТЗ §7, стр. 122:
«Лента наблюдений по активным источникам + фильтр/пометка по стратегии»,
`/v1/monitoring`). Сейчас вью `vMonitoring()` показывает два блока: «Источники»
(живые, из `/v1/sources`) и «Сигналы» — целиком из мок-модели `M.signals`.
Кнопка «Проверить» в проде отключена заглушкой «доступно только через BFF».
То есть половина раздела — витрина без данных.

### 17.1 Источник данных и границы владения

Лента строится по таблице **`public.field_alerts`** (38 строк на 2026-08-28):

    id int PK | source varchar(64) | category varchar(32) | parameter varchar(128)
    value numeric | unit varchar(16) | level varchar(16) | message text
    created_at timestamptz default now()

Наполняют её ВНЕШНИЕ процессы вне этого репозитория
(`/root/.openclaw/workspace/mia_monitor.py`): погода Open-Meteo, NDVI
Agromonitoring, NewsAPI, PriceAPI. В репозитории ERP таблица не упоминается
нигде, миграции на неё нет.

ПОЭТОМУ:
- ERP работает с `field_alerts` ТОЛЬКО НА ЧТЕНИЕ. Никаких POST/PATCH/DELETE.
- Схему НЕ меняем и миграцию на неё НЕ заводим: владелец таблицы — внешний
  скрипт, любая правка столкнёт нас с ним (тот же принцип, что в §16 E).
- ORM-модель объявляется как read-only отражение существующей схемы.

### 17.2 Известное состояние данных (не дефекты нашей реализации)

1. **Лента заморожена.** Свежая запись — 2026-07-12. Производитель пишет в
   `agropilot.field_alerts`, а такой таблицы НЕ СУЩЕСТВУЕТ (есть только
   `public.field_alerts`), поэтому его вставки падают. Починка производителя —
   вне объёма: чужой репозиторий, чужой владелец. Зафиксировать и передать.
2. **`level` в двух регистрах:** 14 `critical`, 12 `warning`, 6 `ok`, 4 `info`
   и по одной `CRITICAL`/`WARNING`. Нормализуем ПРИ ЧТЕНИИ (`lower()`), таблицу
   НЕ трогаем.
3. **`category` содержит смысловые дубли:** `price`/`prices`, `weather`/`frost`.
   НЕ схлопываем и НЕ переименовываем — отдаём как есть, иначе разойдёмся с
   производителем. Схлопывание — предмет отдельной договорённости с ним.
4. **`strategy_tasks` пуста (0 строк)**, значит `monitoring_focus` сейчас пуст
   везде. Пометка по стратегии обязана деградировать мягко: нет ключевых слов —
   лента отдаётся полностью, поле пометки пустое. Пустая лента при пустой
   стратегии — дефект.
5. **Связи `field_alerts.source` -> `sources.id` НЕТ.** `source` — свободный
   текст («Open-Meteo», «Agromonitoring (NDVI)»), в реестре §13 таких записей
   нет. Джойн НЕ изобретаем: отдаём текстовое имя как есть. Привязка наблюдений
   к реестру источников — отдельный контракт, если понадобится.

### 17.3 GET /v1/monitoring — лента

Пагинация обязательна: `data = {items, total, limit, offset}` (§15.5).

Параметры:
    level     info|ok|warning|critical  — сравнение регистронезависимое
    category  <строка>                   — точное совпадение
    source    <строка>                   — точное совпадение
    q         <строка>                   — ILIKE по message + parameter
    since     date (YYYY-MM-DD)          — created_at >= since
    limit     1..200, дефолт 50
    offset    >=0, дефолт 0
Недопустимый `level` -> 422 (как §16). Неразбираемый `since` -> 422 схемой.

Порядок фиксированный: `created_at DESC, id DESC` (лента, новое сверху).
Параметра сортировки нет — вводить только отдельной правкой контракта.

Элемент ленты:
    {id, source, category, parameter, value, unit, level, message, created_at,
     matched_focus: [строки]}
`value` отдаётся числом (numeric -> float) либо null. `level` — нормализованный
нижний регистр. `matched_focus` — см. 17.4.

### 17.4 Пометка по стратегии

Множество ключевых слов = объединение `monitoring_focus` всех строк
`strategy_tasks`. Для каждого элемента `matched_focus` — список тех слов, что
регистронезависимо встречаются в `message`, `parameter` или `category`.

- Слов нет (сейчас — всегда) -> у всех элементов `matched_focus: []`,
  лента отдаётся ПОЛНОСТЬЮ.
- Параметр `focus=true` -> вернуть только элементы с непустым `matched_focus`.
  При пустом наборе слов `focus=true` честно вернёт 0 элементов — это не ошибка.

Пометка вычисляется на лету. Ничего в БД не сохраняется.

### 17.5 GET /v1/monitoring/stats

    {total, by_level: {...}, by_category: {...}, latest_at: <iso|null>}
`by_level` — по нормализованному уровню. `latest_at` — `max(created_at)`,
по нему UI показывает, насколько лента свежа (см. 17.2 п.1).

### 17.6 Frontend

- Флаг `MONITORING_READY` в `js/api.js`.
- В `vMonitoring()` блок «Сигналы» переводится с `M.signals` на живую ленту:
  уровень цветом (critical/warning/ok/info), source + parameter + значение с
  единицей, message, дата. Фильтры по уровню — кнопками, как статусы в лидах.
- Если `latest_at` старше 7 дней — показать явную плашку «данные устарели,
  последнее наблюдение <дата>», чтобы пустая свежесть не выглядела нормой.
- Блок «Источники» НЕ трогаем.

### 17.7 Границы

Вне объёма и НЕ делаем:
- починку производителя `mia_monitor.py` (чужой репозиторий);
- запись/редактирование/удаление наблюдений через API;
- кнопку «Проверить» (живой скан источника) — она задел под BFF, остаётся
  заглушкой;
- «Мой день» зона 3 и счётчики `cntSignals()` — продолжают работать на
  `M.signals`; перевод «Моего дня» на живую ленту — отдельный контракт;
- действие «Действие» по сигналу (`signalAction`) — остаётся на мок-модели;
- привязку наблюдений к реестру `sources` и схлопывание категорий (17.2 п.3, п.5).

DoD 17: ВЫПОЛНЕН 2026-08-28 (реализация a84b8d7 + dc36307).
  [x] GET /v1/monitoring -> {ok,data:{items,total,limit,offset}}, 38 элементов
  [x] level=critical фильтрует и ловит запись в верхнем регистре (CRITICAL)
  [x] level=bogus -> 422, без 500
  [x] category/source/q/since фильтруют; since с битой датой -> 422
  [x] порядок created_at DESC: первый элемент — самый свежий
  [x] matched_focus присутствует у каждого элемента; при пустой strategy_tasks
      лента отдаётся полностью, focus=true возвращает 0 без ошибки
  [x] GET /v1/monitoring/stats: total, by_level нормализован,
      latest_at = 2026-07-11T23:08+00:00 (в серверной зоне +05 это 12.07 —
      psql показывает локально, API отдаёт UTC; расхождения нет)
  [x] раздел «Мониторинг» рендерит живую ленту, плашка устаревания видна
  [x] field_alerts не изменена: 38 строк до и после
  [x] регресс: leads/clients/deals/sources/strategy = 200
  [x] py_compile pass; node --check pass


## 18. Блок B «Справочник» — read-model дерево /v1/catalog

ПРИЧИНА. Последний шаг плана ТЗ §7. Раздела нет ни в backend, ни во фронте:
директории `backend/catalog` не существует, флага `CATALOG_READY` нет.
ТЗ §5.5: единый древовидный архив сущностей, «как проводник Windows»,
**read-only агрегатор поверх существующих реестров, без дублирования данных**.

### 18.1 Что агрегируем и сколько этого есть

Ветки по ТЗ §5.5 и фактические объёмы на 2026-08-28:

    artifacts       21   title,  created_at, owner_id
    content          0   title,  created_at, author_id
    deals           10   name,   created_at, owner_id
    clients          7   name,   created_at
    goals            3   title,  created_at, owner_id
    strategy_tasks   0   title,  created_at, added_by
    sources          1   url,    created_at, added_by   (заголовок = url/handle)
    team             5   name,   created_at            (группировка по role)

Итого 47 листьев. Пустые ветки (`content`, `strategy_tasks`) отдаются с
`count: 0` и НЕ скрываются: пустая ветка — факт о системе, а не повод её прятать.

**Лиды в дерево НЕ входят** — их нет в перечне ТЗ §5.5, и 918 записей утопили бы
остальные 47. Если понадобятся, это отдельная правка контракта с пагинацией.

### 18.2 Модель листа — и чего в ней НЕ будет

    {id, type, title, created_at, owner, link: {route, id}}

`type` — имя ветки в единственном числе (`artifact`, `deal`, `client`, …).
`owner` — из `owner_id` / `added_by` / `author_id`, где такое поле есть, иначе
null. Это идентификатор из `team`, не имя; разрешение в имя — задача фронта.

**Поля `source_agent` из ТЗ §5.5 НЕ БУДЕТ.** Проверено: колонки
`source_agent` нет ни в одной таблице базы, и вывести «MIA / SMM / SPA /
ПЕТРУШКА / человек» не из чего — `owner_id` указывает на человека из `team`,
а не на агента-создателя. Придумывать эвристику — значит отдавать выдумку под
видом факта. Поле вводится отдельной правкой контракта, когда появится источник.

### 18.3 Deep-link: честное ограничение

`link.route` — маршрут фронта для перехода. Карточки существуют НЕ у всех типов.
Проверено по `js/app.objects.js`: одиночные маршруты есть только у `client`,
`deal`, `goal`, `project`.

    client  -> {route: "client", id}    карточка
    deal    -> {route: "deal",   id}    карточка
    goal    -> {route: "goal",   id}    карточка
    artifact-> {route: "artifacts", id} СПИСОК раздела, карточки нет
    content -> {route: "content",  id}  СПИСОК раздела, карточки нет
    source  -> {route: "monitoring", id} СПИСОК (источники живут там)
    team    -> {route: "skills",   id}  СПИСОК (раздел команды)
    strategy_task -> {route: "strategy", id} СПИСОК

Поэтому DoD ТЗ §5.5 п.3 «клик по листу открывает оригинальную карточку»
выполняется ПОЛНОСТЬЮ для client/deal/goal и ЧАСТИЧНО для остальных — открывается
раздел, а не карточка. Создание недостающих карточек — вне объёма Блока B,
это отдельные контракты по разделам.

### 18.4 GET /v1/catalog/tree

    без параметров        -> корень: список веток
    ?node=<branch>        -> содержимое ветки
    ?node=sources:<type>  -> листья подветки источников
    ?node=team:<role>     -> листья подветки пользователей

Узел ветки: `{id, type: "branch", title, count, has_children}`.
`sources` и `team` по ТЗ имеют промежуточный уровень (источники по типам,
пользователи по ролям) — их `?node=` возвращает узлы-подветки, а не листья.
Остальные ветки возвращают листья сразу.

Неизвестный `node` -> 404. Пагинация листьев: `limit` 1..200 (дефолт 100),
`offset`; конверт `{items, total, limit, offset}`.
Порядок листьев: `created_at DESC, id DESC`; узлы веток — в порядке ТЗ §5.5.

### 18.5 GET /v1/catalog/search

    ?q=<строка>  обязателен, минимум 2 символа, иначе 422
    ?type=<тип>  необязательный фильтр по типу листа
    ?limit=      1..100, дефолт 50

ILIKE по заголовку каждой ветки (`title`/`name`/`url`) + по `id`. Возвращает
плоский список листьев модели 18.2 плюс `branch` — в какой ветке найдено.
Конверт `{items, total, limit, offset}`.

Питание палитры `Ctrl+K` этим эндпоинтом — ВНЕ объёма: палитра сейчас целиком
клиентская (`cmdkIndex()` по загруженным `M.*`), её переделка на серверный поиск
меняет поведение всей палитры и требует своего контракта.

### 18.6 Frontend

Раздел «Справочник»: дерево слева (expand/collapse, lazy-load по `?node=`),
превью выбранного листа справа с кнопкой «Открыть» по `link`. Флаг
`CATALOG_READY`. Маршрут `catalog` в навигации.

### 18.7 Границы

- Схему БД НЕ меняем, новых таблиц НЕ создаём, миграций НЕТ: это read-model.
- Дерево read-only: ни drag-n-drop, ни переорганизации (открытый вопрос ТЗ §7 п.2
  закрывается в пользу read-only, как и записано в самом ТЗ §5.5).
- Не трогаем палитру Ctrl+K, разделы-источники этих данных и их API.
- RAG/векторизация «Справочника» — v2, вне объёма (ТЗ, Приложение A).

DoD 18: ВЫПОЛНЕН 2026-08-28 (реализация c8b2271 + e04720b).
  [x] GET /v1/catalog/tree без параметров -> 8 веток с корректными count
      (artifacts 21, content 0, deals 10, clients 7, goals 3, strategy_tasks 0,
      sources 1, team 5)
  [x] ?node=artifacts -> 21 лист, конверт {items,total,limit,offset}
  [x] ?node=sources -> подветки по типам; ?node=sources:news -> листья
  [x] ?node=team -> подветки по ролям; ?node=team:<role> -> листья
  [x] ?node=bogus -> 404, без 500
  [x] пустые ветки content и strategy_tasks видны с count 0
  [x] у каждого листа есть link.route из перечня 18.3
  [x] search?q=<2+ символов> находит по разным веткам; q короче 2 -> 422
  [x] раздел «Справочник» рендерит дерево, lazy-load работает, «Открыть» ведёт
      по link
  [x] БД не изменена: миграций нет, количество строк во всех 8 таблицах прежнее
  [x] регресс: leads/clients/deals/sources/strategy/monitoring = 200
  [x] py_compile pass; node --check pass

---

## §19. Auth — JWT-аутентификация (заменяет STUB get_current_user)

Статус: реализовано 2026-09-14 (предусловие Stage-3 / нового ТЗ от 14.09).

### 19.1 Сущности

- Миграция `016_auth_login.sql`: таблица `team` + колонки `login VARCHAR(64)`
  (уникальный индекс, генерируется как `lower(id)`), `password_hash TEXT` (bcrypt).
- Пароли задаёт оператор: `venv/bin/python -m backend.auth.set_password <login>`
  (интерактивный скрытый ввод, минимум 8 символов).
- Токены: access-JWT (60 мин, `ACCESS_TOKEN_EXPIRE_MINUTES`) и refresh-JWT
  (14 дней, `REFRESH_TOKEN_EXPIRE_DAYS`), HS256, подпись `SECRET_KEY` из окружения.
  Поля payload: `sub` (user id), `name`, `type` (access|refresh), `exp`, `iat`.
  SECRET_KEY не задана или равна заглушке .env.example -> все запросы 401 (fail closed).
- Зависимости: `pyjwt`, `bcrypt` (passlib не используется: конфликт с bcrypt>=4.1).

### 19.2 Эндпоинты (совместимы с js/api.js)

- `POST /v1/auth/login` `{login, password}` ->
  `{access_token, refresh_token, user:{id,name,role,role_key}}`;
  401 UNAUTHORIZED «Неверный логин или пароль» (единая ошибка — не раскрываем существование логина).
- `POST /v1/auth/refresh` `{refresh_token}` -> тот же конвер; 401 при
  просрочке/подделке/неверном типе токена.
- `POST /v1/auth/logout` -> `{detail:"logged out"}` (токены stateless, клиент
  чистит localStorage; серверного отзыва нет).

### 19.3 get_current_user (backend/common/deps.py)

Bearer access-JWT обязателен на всех роутерах с `Depends(get_current_user)`.
401 при: отсутствии заголовка, просрочке, плохой подписи, refresh-токене
вместо access. Возвращает `CurrentUser(id, name)`.

### 19.4 Границы

- RBAC-права по `permissions[]` не меняются — только аутентификация.
- Хранилища отзыва токенов (revocation list) нет — вне объёма.
- Фронт не меняется (login/refresh/logout уже реализованы в js/api.js).

## §17.1a. Поставщик наблюдений — вариант A

Статус: реализовано 2026-09-14. `backend/monitoring/producer/mia_monitor.py`
(замена gbrain-скрипта, закрыты дефекты D1–D9 аудита
docs/MONITORING_PRODUCER_AUDIT.md). Пишет только в
`agropilot.public.field_alerts` (source/category/parameter/value/unit/level/
message/created_at — ровно схема, которую читает §17). Дедупликация по
(source, category, parameter, level) за окно `MIA_DEDUP_MINUTES` (60).
`MIA_MODE=info|critical`. Telegram опционален (`TELEGRAM_BOT_TOKEN` +
`TELEGRAM_CHAT_ID`), сбой TG не роняет запись. Секреты только в окружении.
Ошибки источников логируются; ненулевой код возврата при полном отказе.
Запуск: cron/systemd timer, `python -m backend.monitoring.producer.mia_monitor`.

---

## §20. Медиа-мониторинг A1 (ТЗ v1.1 п. 8.1, Этап 2)

Статус: контракт утверждён 2026-09-14 (Этап 1), реализация — Этап 2.

### 20.1 Сущности

- `sources` РАСШИРЯЕТСЯ (миграция 017): `type` varchar(32) ∈ {news, telegram,
  site, rss} (CHECK), новый `check_period_min int DEFAULT 1440` (периодичность
  сканирования, минуты; 1–3 дня = 1440–4320). Существующая механика
  proposed → approve/reject (§13) сохраняется без изменений.
- Новая таблица `news_items` (миграция 017):
  id serial PK; source_id int FK→sources(id); title text NOT NULL;
  summary text; url varchar(1000); published_at timestamptz; fetched_at
  timestamptz NOT NULL DEFAULT now(); status varchar(16) DEFAULT 'new' CHECK
  ∈ {new, selected, rejected, used}; relevance numeric(4,2) NULL (0..1,
  оценка A1); relevance_reason text; agent_run_id varchar(64).
  UNIQUE(source_id, url) — дедупликация на уровне БД. Индексы: status,
  fetched_at DESC.

### 20.2 Эндпоинты (реализация Этап 2)

- GET /v1/news?source_id=&status=&relevance_min=&limit=&offset= — лента,
  пагинация, дефолт limit 50.
- PATCH /v1/news/{id} {status} — «в работу»/«отклонить»/«использовано»
  (права: content:approve у редактора/руководителя).
- POST /v1/news/scan — запуск сканирования (n8n по расписанию; сервисный
  JWT). Внутри: сбор по активным sources с учётом check_period_min,
  дедуп по UNIQUE, оценка релевантности промтом A1.
- Роль A1: n8n-воркфлоу, расписанием по п. 8.1 ТЗ; промт — реестр промтов §23.

DoD 20.2: ВЫПОЛНЕН 2026-09-14 (первый скан: sources=1, collected=7, inserted=7,
errors=[]; повторный скан inserted=0 — дедуп работает; PATCH /1 selected = ok;
регресс по get_current_user — 401 без токена сохраняется).
Осталось из §20: UI-экран ленты (вью «Маркетинг → Медиа-мониторинг») и
LLM-оценка релевантности вместо keyword-MVP — Этап 2, вместе с A2.

DoD 20.6 (UI): ВЫПОЛНЕН 2026-09-14 — экран «Медиа-мониторинг» (route
medianews, nav 📰): лента с фильтрами по статусу, пагинация, ссылки на
первоисточник, кнопки «В работу»/«Отклонить» (content:approve), ручной
«Сканировать сейчас» (POST /scan). Проверено в браузере под u1: лента 7
материалов, смена статуса через PATCH подтверждена. AGL.loadNews/patchNews/
scanNews + флаг NEWS_READY.

### 20.3 Границы

- Никакого пересечения с полевым мониторингом §17 (field_alerts) — он вне
  скоупа ТЗ v1.1 (домен техкоманды).
- Фильтрация по стратегии — через фиксированный промт-конф
  (chat-strategy-fallback), подключаемый без переделки при появлении блока
  «Стратегии».

## §21. Каналы публикаций и контент (ТЗ v1.1 п. 8.2, Этап 2)

Статус: контракт утверждён 2026-09-14, реализация — Этап 2.

### 21.1 Сущности

- Новая таблица `channels` (миграция 018): id serial PK; type varchar(16)
  CHECK ∈ {telegram, instagram, site}; name text NOT NULL; connection jsonb
  NOT NULL DEFAULT '{}' (chat_id / bot ref и т.п.; секреты — ТОЛЬКО в .env,
  в connection лежит ссылка на имя переменной); adapt_prompt text (промт
  адаптации под канал); active bool DEFAULT true; stats jsonb DEFAULT '{}'.
- `content` (существующая, сейчас пустая) ДОСНАБЖАЕТСЯ в Этапе 2:
  статус-цепочка draft → in_review → approved → scheduled → published,
  versions jsonb (история правок с автором/датой), news_item_id FK
  NULL, channel_ids jsonb, scheduled_at timestamptz, published_url
  varchar(1000). Контракт допишется отдельной ревизией §21 перед Этапом 2.

### 21.2 Границы

- Публикация (A3) — только после явного подтверждения человеком (п. 6.6
  ТЗ); в БД фиксируются время и ссылка.
- Instagram-коннектор — вне объёма (риск-п. 14 ТЗ); schema type допускает.

DoD 21/A3 (паблишер): ВЫПОЛНЕН 2026-09-14 (миграция 022): POST
/v1/content/{id}/publish — отправка approved/scheduled поста через Bot API
бота JARVIS_MONITOR в TELEGRAM_CHAT_ID (или явный chat_id), право
content:approve, status=published + published_at + published_url (tg://),
версия «опубликовано». Live: пост опубликован (msg 2363), повторная
публикация published-поста корректно отклонена 422. Фронт: кнопка
«🚀 Опубликовать в Telegram» с confirm. Критерий приёмки ТЗ №1 выполнен:
источник → NewsItem → черновик → правка → публикация в Telegram без
ручных вставок. A3-адаптация текста под канал (LLM) — при шлюзе §10.

DoD 21 (календарь публикаций): ВЫПОЛНЕН 2026-09-14 — вкладка «📅 Календарь»
раздела «Контент»: месяц-сетка (неделя с Пн), посты по scheduled_at,
сегодня выделено; правая колонка «Без слота»; назначение: клик по посту →
клик по дню (PATCH scheduled_at, approved→scheduled автоматически).
MVP-замена drag-and-drop клик-назначением (перенос DnD — v2 при
необходимости). Проверено live: slot 2026-09-16 10:00 записан в БД.

## §37. Сегменты аудитории и рубрикатор для A2 (гэп №2 концепта SSM)

Статус: реализовано 2026-09-17 (миграция 035). Дефолты (вопросы без
ответа владельца, ветал допустим): удаление сегмента — автоотвязка связей
со счётчиками; рубрики — такой же управляемый справочник; тексты сидов
сегментов — по концепту apilot92.

- audience_segments: code/name/description/prompt_addon (язык/CTA для
  A2)/active; сиды vine («сигнал + что делать сегодня»), grain («окно 72
  часа»), greenhouse («связь внешней и внутренней погоды»). rubrics: 9
  сидов (сигнал недели … полив и окна операций).
- Привязка: sources.segment_code (модалка «+ Источник»), channels.
  segment_code (PATCH); news_items.segment_code наследуется при скане;
  content.segment_code/rubric_code. Разрешение сегмента в from_news:
  payload -> новость -> источник.
- Генерация: from_news и POST /v1/content/{id}/regen_segment добавляют к
  промту A2 блок «СЕГМЕНТ АУДИТОРИИ (…): <addon>» и «РУБРИКА: …»;
  regen_segment переписывает существующий пост (старый текст — версией).
- CRUD /v1/segments, /v1/segments/rubrics — право контент-мейкера
  (content:edit/content:approve/manager/admin). /rubrics объявлены РАНЬШЕ
  /{segment_id} (матчинг FastAPI). DELETE сегмента/рубрики: связи
  отвязываются (SET NULL), счётчики в ответе.
- UI: селекты сегмента/рубрики в редакторе поста + кнопка «✍ Переписать
  под сегмент/рубрику (A2)»; справочник в разделе «Контент» (карточки
  сегментов с паузой/удалением, рубрики, добавление); сегмент в модалке
  «+ Источник».

DoD 37: live 17.09 — справочники (3+9); пост #6 из news 8: from_news с
vine/weather_todo («Уважаемые виноградари Крыма и Анапы!»), regen_segment
-> grain («Уважаемые фермеры Краснодарского края!», «72 часа») — стиль
сегмента применяется, версии пишутся.

## §36. Медиа-мониторинг: тулбар источников + карточка новости

Статус: реализовано 2026-09-17 (без миграций; решения владельца: удаление
источника — каскадом с новостями).

- Тулбар «Управление источниками» над фильтрами ленты: «+ Источник»
  (модалка как в Мониторинге), выбор источника, «✕ Удалить источник (с
  новостями)» с подтверждением.
- DELETE /v1/sources/{id} теперь ПОЛНОЕ удаление: сначала news_items
  источника, затем сам источник (было: soft-disable). Посты контента,
  созданные из новостей, остаются.
- Карточка новости вертикальная: 1-я строка — источник (pill) + статус +
  релевантность; 2-я — тема (title, ссылка); 3-я — анонс (140 символов):
  при наведении всплывающий фрейм с кратким содержанием (summary до 400
  символов; JS mouseenter/mouseleave, т.к. group-hover в scanned CSS нет).
- Кнопки операций («В работу»/«Отклонить»/«В пост») — в подвале карточки.

DoD 36: фронт на проде (v=1789610400) отдаёт тулбар и новые карточки;
каскадное удаление проверено на live-источнике при следующей зачистке.

## §35. Согласование постов в Telegram со SLA (гэп №1 концепта SSM)

Статус: реализовано 2026-09-17 (миграция 034). Решения владельца: канал
выбирается при отправке; «Отложить» = approved + слот в календаре;
срочность авто (связанная новость relevance >= 0.7) с ручным
переопределением; кнопки — только владелец (его чат).

- POST /v1/content/{id}/submit_review {channel_id?, urgent?}: пост ->
  in_review, владельцу в TG сообщение с inline-кнопками
  [✅ Опубликовать][✏️ Правка][⏰ Отложить], SLA: срочно 15 мин / планово
  2 ч (дедлайн в тексте по МСК); повторная отправка закрывает прежний
  pending как expired(resubmit).
- content_approvals: urgent, auto_urgent, channel_id, sent/deadline,
  status pending|approved|rejected|deferred|edited|expired, tg_message_id,
  decided_*. GET /v1/content отдаёт последнюю approval в карточке.
- Кнопки обрабатывает tg_poller (callback_query, каждые 5 мин):
  «Опубликовать» -> POST /publish {channel_id} (сервисный u7, публикация
  в выбранный канал); «Правка» -> draft (approval=edited); «Отложить» ->
  approved (deferred), слот — в календаре публикаций. Ответ кнопки +
  editMessageText с итогом; повторное нажатие — «уже обработано».
- SLA: pending с истёкшим дедлайном -> expired + пометка сообщения в TG
  («решение в системе»); пост остаётся in_review, в UI красный бейдж
  «⏰ SLA истёк — решите вручную».
- UI: кнопка «📤 На согласование (TG)» на карточке поста (draft/in_review),
  модалка: канал из справочника channels или создание нового
  (имя + chat_id), срочность «Авто / 15 мин / 2 ч»; бейджи статуса
  согласования на карточке.

DoD 35: live 17.09 — submit_review поста #5 (срочный, канал DoD,
msg 2440 в TG владельца, approval pending, дедлайн 09:21 МСК); решения
кнопками применяются tg_poller'ом (<=5 мин); SLA-истечение —
автоматически.

## §34. MIA — погодный агро-консультант (замена §17 field_alerts)

Статус: реализация 17.09 (миграция 033). Решения владельца: Open-Meteo
(без ключа), 06:00 МСК ежедневно (24 ч), пн/чт (72 ч), пн (120 ч),
получатель — TG-чат владельца, старая механика §17 заменена целиком
(таймер mia остановлен; лента field_alerts остаётся как read-only архив).

- Справочники (все — CRUD, оператор пополняет сам): crops (код+название),
  geo_points (название+lat/lon), crop_phases (фенофаза по месяцам
  культуры, MVP-календарь), crop_rules (детерминированные правила:
  kind=risk|window, metric temp_min/temp_max/precip_sum/humidity_avg/
  wind_max, op, threshold, severity info|warn|critical, текст рекомендации),
  meteo_subscriptions (точка+культура+horizons int[] из {24,72,120}).
- Пайплайн POST /v1/meteo/run {point_id, crop_code, horizon_h, send}:
  Open-Meteo hourly (temperature_2m, precipitation, relative_humidity_2m,
  wind_speed_10m; timezone Europe/Moscow) -> агрегаты по горизонту ->
  правила с учётом фенофазы месяца (МСК) -> weather_runs (metrics/risks/
  windows, critical при severity=critical) -> LLM-резюме «Плюсы/Минусы/
  Рекомендации» (агент a-mia, реестр §29, лог §32/§33) -> Telegram.
- GET /v1/meteo/latest (для UI), GET /v1/meteo/runs (история), CRUD:
  /v1/meteo/points, /crops, /rules, /subs, /phases. Справочники и запуск —
  manager/admin; просмотр — все аутентифицированные.
- Расписания (systemd, шаблон agropilot-meteo@.service + таймеры):
  @24 — ежедневно 06:00 Europe/Moscow; @72 — Mon,Thu 06:00; @120 — Mon
  06:00. CLI: python -m backend.meteo.run_forecast --horizon N (сервисный
  вход u7, прогоняет все активные подписки с этим горизонтом, send=true).
- Границы v1: правила однофакторные (окна комбинирует LLM в тексте);
  фенофаза календарная (ручная корректировка — v2); кнопка «резюме -> в
  пост A2» — v2; ночной контроль заморозков вне расписания — v2.

DoD 34: ВЫПОЛНЕН 2026-09-17 (деплой d042672, миграция 033: 3 культуры,
9 правил, подписка ЮБК-виноград 24/72/120). Live: ручные прогоны 24/72/120 —
агрегаты Open-Meteo (Ялта 17-24 C, фенофаза «Уборка» — сентябрь верно),
риски/окна посчитаны, LLM-резюме структурные; send=true — сводка доставлена
в TG (telegram_sent=true); правило сильного ветра (>10 м/с) добавлено и
сработало; таймеры @24/@72/@120 в list-timers (06:00 МСК); карточка a-mia
логируется в дашборде (4 записи). Старый agropilot-mia.timer отключён.

## §33. Дашборд агентов v2 — алерты, графики, качество промтов

Статус: реализовано 2026-09-16 (без миграций: поверх run_logs/content_versions/
agent_cards.limits §32/§21/§29).

- GET /v1/agents/dashboard/summary расширен:
  - `daily`: ровно 14 записей {date, runs, errors, tokens, cost_usd} — дни
    по Europe/Moscow (рабочее время системы, решение владельца 17.09),
    нулевые дни заполнены.
  - `alerts`: [{agent_code, kind, value, limit, message}]; kinds:
    cost_day/cost_week/tokens_day/errors_day (превышение лимитов) и
    silent («молчит N ч» — агент с расписанием без прогонов дольше
    интервала+1ч).
  - Лимиты: agent_cards.limits (JSONB) сливаются с дефолтами
    _LIMIT_DEFAULTS (cost_usd_day 1.0, cost_usd_week 5.0, tokens_day 200k,
    errors_day 5); значение 0 в карточке отключает контроль. Переопределение
    — PATCH /v1/agents/{code} (limits).
  - Расписание для staleness: _SCHEDULE_H (a1 — 1 ч, a6 — 24 ч); прочие
    агенты работают по запросу, stale не считается. В карточках ответа
    появились expected_every_h и stale_hours.
  - `edits`: метрика качества черновиков A2 за 14 дней из content_versions:
    contents (черновиков), edited (правились), avg_revisions (правок на
    черновик), untouched_pct (% без правок). Версии после первой считаются
    правками.
- UI: блок «Агенты A1–A7» — блок «Алерты агентов» (только при наличии),
  плашки «молчит N ч» на карточках, столбики запусков по дням (14 дней,
  ошибки красным, tooltip с токенами/стоимостью), карточки метрик
  «Качество черновиков A2».
- pytest: tests/test_agents_dashboard.py (7 тестов: слияние лимитов, алерты
  cost/tokens/errors, отключение лимитом 0, staleness по расписанию/паузе/
  мусорной дате). Итого tests/ — 15 passed.

DoD 33: ВЫПОЛНЕН 2026-09-17 (деплой da7c673, рестарт backend). Live:
summary отдаёт daily/alerts/edits/stale_hours; метрики на реальных данных
(edits: 3 черновика/2 правились/avg 1.0/33.3% без правок; алерт
«a1 молчит 14.9 ч» корректно подсветил сбой n8n — см. HANDOVER 17.09).

## §32. Дашборд мониторинга агентов (TZ_agents_dashboard_v1.0.md)

Статус: реализовано 2026-09-16 (миграция 032).

- run_logs: журнал запусков (статус/ошибка/модель/prompt+completion+
  total tokens/cost_usd/items/meta). llm_call_logged — LLM-вызов с usage
  (прайс gpt-4o-mini, прочие модели — cost 0 до настройки прайса);
  log_run — процессные прогоны.
- Логирование: A1 (scan, items), A2/A3 (from_news/adapt), A4 (classify),
  A5 (generate), A6 (digest), A7 (ask).
- GET /v1/agents/runs/all (фильтры agent/status), GET /v1/agents/
  dashboard/summary (по агентам 24ч/7д + лента 15 + тоталы недели).
- UI: блок «Агенты A1–A7» в разделе «Дашборд» — карточки (запуски/ошибки/
  токены/стоимость/items/последний запуск) + лента запусков. Live:
  A1-скан и A7-запрос залогированы, блок отрисован в браузере.
- Прочее: cache-busting версий скриптов в index.html (?v=unixtime) —
  конец проблем со stale-кэшем фронта.

## §31. Хвосты: channels-CRUD, TG-коннектор входящих, pytest

Статус: реализовано 2026-09-16.

- **channels-CRUD** (§21.1): GET/POST/PATCH/DELETE /v1/channels; токены в
  connection запрещены (422), только token_env-ссылки. Публикация
  (POST /content/{id}/publish) принимает channel_id -> connection.chat_id.
  Live: create/delete проверены; фикс created_at (server_default).
- **TG-коннектор входящих** (§22): backend/inbound/tg_poller.py — getUpdates
  каждые 5 мин (agropilot-tg-inbox.timer), сообщения приватных чатов ->
  inbounds (channel=telegram, дедуп по tg message_id, служебный чат
  владельца и боты фильтруются). A4-классификация в UI по кнопке.
- **pytest**: tests/test_parsers.py (8 тестов: парсеры t.me/RSS, ЕГРЮЛ с
  моками, рендер шаблонов артефактов с missing, уровни mia_monitor,
  bcrypt roundtrip). Запуск: venv/bin/python -m pytest tests/ -q —
  8 passed. Зависимость pytest добавлена в venv сервера.

## §30. Блоки «Стратегии»/«Цели» (следующий этап ТЗ v1.1)

Статус: реализовано 2026-09-16 (миграция 029).

- strategy_directions: CRUD /v1/strategy/directions (title/description/
  keywords/status/goal_ids/owner). Сид: SD1 «Аграрная тема»,
  SD2 «Применение нейросетей» (медиаполитика встречи, ТЗ 8.2).
- goals read-write: POST /v1/goals, PATCH /{id} (direction_id/target/unit/
  current; прогресс пересчитывается из current/target, clamp 0-100).
  Модель дополнена direction_id/target/unit/current (миграция 029;
  был баг: поля отсутствовали в ORM — PATCH молча не сохранял, исправлено).
- Фильтрация по стратегии (ТЗ 8.1): A1 при отсутствии у источника своих
  ключевых слов использует слова активных направлений (до 30).
- UI «Стратегия»: направления с целями-карточками, прогресс-бары,
  ± с адаптивным шагом (1% от target), +Направление, стратегические
  задачи. Live: SD1/SD2 с целями G1-G3, прогресс ± работает.

## §29. Карточки агентов и промты (ТЗ п. 6.4/8.9)

Статус: реализовано 2026-09-15 (миграция 028).

- agent_cards (сид a1..a7: name/role/model/limits/active) + prompts
  (UNIQUE(agent_code, version), автор и дата у каждой версии).
- GET /v1/agents (карточки + текущий промт/версия); PATCH /v1/agents/{code}
  (name/role/model/limits/active); GET /{code}/prompts (история, откат =
  PUT со старым текстом); PUT /{code}/prompt — новая версия.
  Право: admin или agents:manage (u1-manager получает 403).
- Runtime: A2/A3/A4/A7 читают промты из реестра (кэш 60 с, fallback на
  константы llm.py). Сид v1 — из констант; live: v2 для A7 записана и
  подхвачена ассистентом (ответ стал короче по новому стилю).

DoD 29 (UI): ВЫПОЛНЕН 2026-09-15 — «Настройки» → секция «Агенты A1–A7»:
карточки (модель/версия промта), textarea промта + «Сохранить новую
версию» (PUT, право agents:manage); карточка клиента — «📋 Заполнить
реквизиты по ИНН (ЕГРЮЛ)»; карточка сделки — «📄 Создать артефакт
(КП/письмо/договор)» (POST /v1/artifacts/generate, переход в Артефакты,
toast со списком missing-переменных). Проверено в браузере под u1.

## §28. Чат-ассистент A7 (ТЗ v1.1 п. 8.8)

Статус: реализовано 2026-09-15.

- POST /v1/assistant/ask {question}: срез контекста (сделки по этапам +
  горячие, клиенты, лиды по статусам, задачи просрочено/сегодня,
  входящие новые, контент по статусам, новости медиа-мониторинга за 14
  дней с матчингом по основе слова) -> LLM, отвечающая только по данным.
- Чат ПЕТРУШКИ (owlAsk) в apiMode идёт через A7; orchChat/petReply —
  fallback (старый путь сохранён).
- Live: «сколько сделок в работе» -> 8 (точно по данным); «что нового по
  орошению и вебинарам» -> пересказ реальных материалов мониторинга.

## §27. Агент артефактов A5 (ТЗ v1.1 п. 8.6)

Статус: реализовано 2026-09-15 (миграция 027, 0 ошибок).

- artifact_templates: код/тип/шаблоны заголовка и текста с переменными
  {{deal.*}}/{{client.*}}; сид: kp, letter, contract. CRUD:
  GET/POST /v1/artifacts/templates.
- POST /v1/artifacts/generate {template_code, deal_id}: контекст = сделка
  + клиент (+реквизиты ЕГРЮЛ §26), результат Artifact status=draft
  (draft -> approved -> sent через существующий PATCH), незаполненные
  переменные в missing. Отправка — только вручную после правки (п. 8.6).
- artifacts: +body, +client_id. Live: КП по «Капельное орошение 12 га»
  сгенерировано, поля сделки подставлены.

## §26. Реквизиты клиента по ИНН — открытый ЕГРЮЛ (ТЗ v1.1 п. 8.4)

Статус: реализовано 2026-09-15 (решение владельца: вариант 2, открытый
источник; Контур/DaData — при росте объёма).

- Миграция 026: clients.inn varchar(12) + requisites JSONB.
- backend/clients/egrul.py: неофициальный JSON-разбор egrul.nalog.ru
  (POST query -> токен -> /search-result/{t}, поля n/c/o/p/r/g/rn).
  Без ключей; при смене формата или капче — честная EgrulError, оператор
  вводит вручную (fallback по ТЗ п. 14).
- POST /v1/clients/{id}/requisites {inn?} — заполняет inn + requisites
  (наименование/ОГРН/КПП/дата рег./руководитель/регион); name/region
  перезаписываются только если пустые. 422 при плохом ИНН/сбое источника.
- Live: Сбер (7707083893) — все поля заполнены; плохой ИНН — 422.
  Тестовые записи с C1/C2 вычищены.

## §25. «Мой день» + агент напоминаний A6 (ТЗ v1.1 п. 8.7)

Статус: реализовано 2026-09-15.

- GET /v1/myday/digest?user_id= — агрегат: задачи просрочено/сегодня/скоро
  (фильтр по владельцу), горячие сделки (score>=70), необработанные
  входящие, посты на правке.
- POST /v1/myday/digest {send, user_id, tone} — то же + LLM-сводка
  (тон: env A6_TONE или разовый параметр tone); send=true -> Telegram.
- Расписание: agropilot-a6.timer, ежедневно 07:30 Europe/Moscow (правка
  17.09: сервер в Алматы, но рабочее время системы — МСК; TZ задана явно
  в OnCalendar), CLI
  python -m backend.myday.send_digest (сервисный вход u7, U7_PASSWORD в .env).
- Live: сводка из реальных данных (6 просроченных, 3 горячие сделки),
  telegram_sent=true (CLI и API).

## §24. LLM-шлюз (OpenRouter)

Статус: реализовано 2026-09-14.

- `backend/common/llm.py`: единая точка LLM-вызовов `llm_chat(prompt, system,
  model, max_tokens)` -> OpenRouter chat-completions. Конфиг в окружении:
  OPENROUTER_API_KEY, LLM_MODEL (по умолчанию openai/gpt-4o-mini),
  LLM_TIMEOUT_SEC. Ключи только в .env. Исключения LLMNotConfigured/LLMError.
- Промты A2/A3 — константы в llm.py (§6.4: промт = конфигурация; реестр
  prompts в БД с версионированием — Этап 4, вызовы не меняются).
- A2: POST /content/from_news генерирует черновик LLM (fallback: копия
  материала при сбое/отсутствии ключа, с пометкой в content_versions).
- A3: POST /content/{id}/adapt {prompt?} — адаптация текста под канал;
  прежний текст сохраняется версией; опубликованное адаптировать нельзя.
- Live-проверки: генерация поста из news_id=3 (переработанный текст, не
  копия), адаптация под Instagram, версии зафиксированы.

## §22. Входящие обращения + A4 (ТЗ v1.1 п. 8.3, Этап 3)

Статус: контракт утверждён 2026-09-14, реализация — Этап 3.

- Новая таблица `inbounds` (миграция 019): id serial PK; channel varchar(16)
  CHECK ∈ {telegram, email, site, social, call}; contact varchar(200);
  subject varchar(500); body text; received_at timestamptz NOT NULL
  DEFAULT now(); status varchar(16) DEFAULT 'new' CHECK ∈ {new,
  in_progress, converted, spam}; assigned_to varchar(16) FK→team(id) NULL;
  client_id int NULL; lead_id int NULL; dedup_key varchar(200) (уникально
  где не NULL — дедуп по контакту+тексту); a4_class jsonb (тема/срочность/
  похожий клиент — черновик классификации A4).
- Эндпоинты (Этап 3): GET /v1/inbound (очередь, фильтры), POST /v1/inbound
  (ручное добавление звонка), PATCH /v1/inbound/{id} (статус,
  ответственный), POST /v1/inbound/{id}/convert → лид (переиспользует
  §15.6 POST /v1/leads, не дублирует).
- Привязка к известному клиенту — по контакту из карточки (client_id),
  отображение в истории карточки.

DoD 22 (Входящие + A4): ВЫПОЛНЕН 2026-09-15 (миграция 023, 0 ошибок):
- POST /v1/inbound (дедуп sha1 channel+контакт+текст, 409 на дубликат),
  GET с фильтрами, PATCH (status/assigned/client_id)
- POST /{id}/classify: A4-LLM (topic/urgency/is_spam/reply_draft),
  авто-спам при is_spam=true
- POST /{id}/convert: лид B<N> по схеме §15.6, inbound->converted + lead_id (FK)
- UI «Входящие»: живая очередь (мок — только в демо-режиме), фильтры,
  кнопки «Классифицировать (A4)» / «→ В лид» / «Спам», карточка A4 с
  черновиком ответа. Live: обращение -> A4 -> лид B917, проверено в браузере.

## §16a. Воронка сделок ТЗ v1.1 (6 этапов)

Аудит 15.09: действующие 8 кодов §16 = 6 этапов ТЗ (lead/assess/proposal/
deal/won/service = Зацепка/Оценка/Договор/Проектирование/Реализация/Сервис)
+ 2 терминальных статуса (lost, cancelled). Канбан строится по этим 6
этапам. Переименование кодов и миграция данных НЕ требуются — цель ТЗ
(воронка из 6 этапов) достигнута без риска для 914 лидов и истории сделок.

## §23. Роли и пермиссии (ТЗ v1.1 п. 4/5)

Статус: применено 2026-09-14 (Этап 1).

### 23.1 Карта ролей → team

| Роль ТЗ | team | role_key | perms-профиль |
|---|---|---|---|
| Руководитель Р. | U6 (создать, admin) | admin | все |
| Разработчик П. | U7 (создать, admin) | admin | все + agents:manage |
| Редактор (Оксана) | U2 Оксана | manager + content:approve, sources:approve | конвейер контента |
| Оператор (Катя) | U1 Екатерина | manager (текущий) | inbound:*, clients:*, leads:* |
| SMM-поддержка | U4 Марина | smm | content:edit |
| Инженеры | U3 Дмитрий, U5 Сергей | engineer | без изменений |

Пользователи U6/U7 созданы с именами-плейсхолдерами «Р.» и «П.» —
переименовать при первом входе. Пароли — set_password (отчёт Этапа 1).

### 23.2 Конвенция пермиссий

`permissions[]` в team: строки вида `block:action` (content:approve,
sources:approve, agents:manage, inbound:convert...). Роутеры проверяют
через _is_manager-паттерн (§11) или явную пермиссию; полный RBAC-маппинг
наращивается по мере появления блоков. Сервисные вызовы агентов (n8n) —
JWT служебной учётки U7, лимит: только whitelist эндпоинтов
(POST /v1/news/scan и т.п.), при расширении — ревизия контракта.
