# ROADMAP — Этап-2 (M10): бэклог по оставшимся 404-эндпоинтам

> Составлено 2026-07-17 после закрытия issue#1 (Этап-1).
> Основание: фактические HTTP-статусы с прода `https://mdked.hlab.kz/agropilot/api/v1/*`,
> ожидания фронта из `js/api.js` (loader-методы), паттерн `backend/deals` + `backend/team`/`backend/goals`.
> Все новые роутеры монтируются в `backend/main.py` под `prefix="/agropilot/api/v1"`,
> отдают конверт `{ok, data}` (`backend/common/errors.py`), используют `Depends(get_db, get_current_user)`.

## Легенда приоритетов
- **P1** — раздел меню виден пользователю и сейчас пуст/деградирует; бизнес-ценность Этапа-2.
- **P2** — AI/оркестратор-слой, повышает качество, но UI работает и без него (safeLoad-фолбэк).
- **P3** — вспомогательное/инфраструктурное.

## Статус эндпоинтов на 2026-07-17
| Эндпоинт | Статус | Раздел UI | Действие M10 |
|---|---|---|---|
| `/v1/clients` | 404 | Клиенты | НЕ реализовывать как таблицу — фронт `loadClients()` деривит из `/v1/deals`. Задача M10-1: перевести на первичный источник. |
| `/v1/sources` | (нет) | БЛОК-1 Мониторинг | M10-2: реестр источников (ядро Этапа-2) |
| `/v1/content` | 404 | Контент и соцсети | M10-3 |
| `/v1/packages` | 404 | Упаковки | M10-4 |
| `/v1/artifacts` | 404 | Артефакты | M10-5 |
| `/v1/reports` | 404 | (отчёты) | M10-6 |
| `/v1/orchestrator/digest` | 404 | ПЕТРУШКА header | M10-7 |
| `/v1/orchestrator/recommendations` | 404 | ПЕТРУШКА подсказки | M10-8 |
| `/v1/health` | 404 | API-бейдж | M10-9 |
| `/v1/skills` | 404* | Навыки команды | *на проде живёт как `/v1/team/skills` (→200, §14). Задача M10-10: сверить путь фронт↔бекенд. |

---

## M10-1 · Clients — первичный источник (P1)
- **Проблема:** `/v1/clients` = 404; фронт деривит клиентов из сделок → нет клиентов без сделок, health всегда `green`, поля пустые.
- **Задачи:**
  - `backend/clients/{models,routes,__init__}.py` по паттерну deals; таблица `clients` уже засеяна (C1–C5, seed_prod.sql).
  - `GET /clients`, `GET /clients/{id}`; поля: `id,name,industry,region,need[],health,deals_count`.
  - `js/api.js`: `loadClients()` → `safeLoad('/v1/clients?limit=200')` с текущим deals-деривом как фолбэк.
- **Критерий:** `/v1/clients`→200; раздел «Клиенты» показывает C1–C5 с реальным health.

## M10-2 · Sources — реестр источников мониторинга (P1, ядро Этапа-2)
- **Проблема:** `loadSources()`/`createSource()` есть на фронте, бекенда нет; онбординг «+ Источник» и БЛОК-1 не работают.
- **Задачи:**
  - Миграция `sources` (тип: site/rss/telegram/tender, url/handle, keywords[], active, created_at).
  - `backend/sources/{models,routes}.py`: `GET /sources`, `POST /sources`, `PATCH /sources/{id}`, `DELETE /sources/{id}`.
  - Auth-правило записи как в team/skills (user=Depends, admin-bypass TODO).
- **Критерий:** источник создаётся из UI, сохраняется в БД, отображается в «Мониторинг».

## M10-3 · Content — контент и соцсети (P1)
- **Задачи:** миграция `content` (title, channel, status draft/review/published, body, deal_id?, created_at); `GET/POST /content`, `PATCH /content/{id}`.
- Связка с AI-черновиком (см. M10-8 `/content/{id}/ai/draft`).
- **Критерий:** `/v1/content`→200; раздел «Контент» рендерит список, кнопка создания сохраняет в БД.

## M10-4 · Packages — упаковки (P1)
- **Задачи:** миграция `packages` (name, industry, status, deal_id?, items JSON); `GET/POST /packages`, `PATCH /packages/{id}`.
- Учесть frontend-контракт `vPackages()` (`js/app.objects.js`).
- **Критерий:** `/v1/packages`→200; «Упаковки» показывают данные, создание работает.

## M10-5 · Artifacts — артефакты (P1)
- **Задачи:** миграция `artifacts` (kind КП/договор/схема, deal_id, url/blob-ref, created_at); `GET/POST /artifacts`.
- **Критерий:** `/v1/artifacts`→200; «Артефакты» рендерит `vArtifacts()`.

## M10-6 · Reports — отчёты (P2)
- **Задачи:** `GET /reports` (агрегаты по сделкам/целям), read-only.
- **Критерий:** `/v1/reports`→200 или явное решение оставить на safeLoad-фолбэке.

## M10-7 · Orchestrator digest (P2)
- **Проблема:** `aiDigest()` → 404 → шапка ПЕТРУШКИ без агрегата.
- **Задачи:** `GET /orchestrator/digest` → сводка дня (сигналы, просрочки, черновики). Может быть детерминированным до подключения LLM.
- **Критерий:** `/v1/orchestrator/digest`→200 c `{text|items}`.

## M10-8 · Orchestrator recommendations + AI-actions (P2)
- **Задачи:**
  - `GET /orchestrator/recommendations` → массив подсказок (`kind,grade,title,deal_id`) для `owlPush`.
  - Проработать deal-AI actions, уже вызываемые фронтом: `/deals/{id}/ai/{score,enrich,followup,generate-kp,generate-contract}`, `/content/{id}/ai/{draft,trends}`, `/orchestrator/{chat,feedback}`.
- **Критерий:** подсказки ПЕТРУШКИ приходят с сервера; хотя бы `score`/`followup` дают реальный ответ.
- **Зависит от:** обязательное цитирование (M10-роадмап) для AI-ответов.

## M10-9 · Health-check (P3)
- **Задачи:** `GET /health` → `{ok:true, version, db:up}`; `js/api.js.status()` уже ждёт `/agropilot/health` — согласовать путь.
- **Критерий:** API-бейдж в шапке показывает живой статус.

## M10-10 · Skills path reconciliation (P3)
- **Проблема:** фронт может звать `/v1/skills`, а бекенд отдаёт `/v1/team/skills` (→200 в §14).
- **Задачи:** сверить фактический вызов в `js/api.js`/`app.objects.js` с роутером `skills_router`; выровнять путь либо добавить алиас.
- **Критерий:** раздел «Навыки» грузится без 404.

---

## Кросс-задачи Этапа-2 (из установки заказчика)
- **Обязательное цитирование** — AI-ответы (M10-7/8) возвращают source-ссылки; ввести в контракт orchestrator.
- **agent_questions** — механизм уточняющих вопросов агента; отдельная миграция + роутер.
- **Монитор мультиопыта** — поверх M10-2 (sources): агрегация сигналов из источников.
- **Knowledge base** — хранилище знаний; связать с артефактами (M10-5) и цитированием.

## Порядок реализации (предложение)
1. M10-2 Sources (ядро) → 2. M10-3 Content → 3. M10-4 Packages → 4. M10-5 Artifacts → 5. M10-1 Clients →
6. M10-7/8 Orchestrator + цитирование → 7. agent_questions → 8. M10-6 Reports → 9. M10-9/10 инфра.

## Durable-правила (перенос из HANDOVER §15)
- Новые роутеры — по паттерну `backend/deals`: `AsyncSession`, `Depends(get_db, get_current_user)`, `{ok,data}`, `NotFoundError`.
- Регистрация в `backend/main.py` под `/agropilot/api/v1`; активация = `systemctl restart agropilot-backend.service`.
- Рабочий сервис — `agropilot-backend.service` (venv), НЕ `agropilot.service` (masked).
- После правок — `py_compile`/`node --check`, push, raw-проверка контента, повторный runtime-QA.
