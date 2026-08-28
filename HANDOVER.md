# HANDOVER — AgroPILOT / A PILOT (АгроЭлемент). Перенос состояния в новую сессию
Дата: 2026-07-08 · Обновлено: 2026-07-17 · Репозиторий: github.com/volhover-crypto/agropilot-web (ветка main)

## 0. Статус
- Репозиторий создан и наполнен (подтверждено на github.com и github.dev): assets/, css/, js/, index.html. 1 commit (0434555).
- Ветка по умолчанию: main ✅ (переименовано 2026-07-12, M8: создана ветка main на HEAD d950a860, default branch обновить в настройках GitHub Settings → Branches).
- Ветка master: удалена 2026-07-12 ✅ Тег legacy/master → 1f571255 сохранён.
- Ограничение: правки прод-исходников — ТОЛЬКО с явного подтверждения пользователя.
- **PROD LIVE ✅ (2026-07-13):** backend поднят на живом сервере, frontend-флаги `CALENDAR_READY`, `SKILLS_READY`, `STRATEGY_READY` активированы коммитом `a6d5ed01`; smoke test дал три `200` на `/agropilot/api/v1/calendar`, `/agropilot/api/v1/team/skills`, `/agropilot/api/v1/strategy`.
- **PROD STABLE ✅ (2026-07-17):** issue#1 полностью закрыт; backend переведён на systemd (`agropilot.service`), переживает ребут сервера; seed-данные в PostgreSQL.

## 1. Что за система (факт из кода)
Объектно-ориентированный агро-B2B рабочий стол. Стек: Alpine.js (без сборки), Tailwind/Pico, ванильный JS, строковый innerHTML-рендер, hash-роутинг.
Файлы: index.html (auth-guard, login-модал, темы); js/api.js (REST-клиент BFF :5555, /agropilot/api); js/app.objects.js (~130КБ ядро: state+resolvers+вьюхи); js/mock.objects.js (window.MOCKO демо-модель).
Иерархия (mock header): Стратегия → Цели → Проекты/Сделки/Концепции → Задачи → Артефакты; мягкая связь по industry+need_type.
Режимы: apiMode true(BFF)/false(mock); fallback на mock при пустом/ошибочном ответе; retry+refresh на 401/403. Персист localStorage ключ agropilot_data_v1 (persist/restore).
AI: один модератор ПЕТРУШКА (Level-2) + LLM-эндпоинты (orchChat, aiScore/enrich/followup/generate-kp/contract, aiDigest, aiRecommendations). Градации AUTO/CONFIRM/HINT. Эвристика petReply() при !apiMode.
Резолверы: clientById, clientName(c)=c.name||c.title||c.id, dealById; агрегация objActivity()+vTimeline()+activityBlock().

## 2. Изначальная установка (заказчик)
Мультиагентная офисная система цифровых фамильяров для A PILOT/АгроЭлемент (Крым/Кубань), замещающая ERP/CRM/финучёт/планировщики/вики/контроль версий/календари/коммуникации. Малая команда; люди=стратегия+верификация. ШАГ-1 = план реализации, пошагово с верификацией.

## 3. Ключевые решения диалога
- Путь B (объектный стол + один модератор ПЕТРУШКА) как эволюционный мост к A (мультиагенты). НЕ возвращаться к A первым шагом. Порог B→A: навык стабильно высокий объём+качество в CONFIRM/AUTO → выделять в отдельного фамильяра.
- Новые вводные заказчика (обязательны):
  1) IoT ИСКЛЮЧАЕТСЯ полностью (нет датчиков/телеметрии). В модели IoT-объектов нет — чистка терминологическая.
  2) Все заглушки → реальные BFF-объекты или удалить.
  3) Правки только в исходники (без сборки).
  4) 4 крупных блока жизненного цикла клиента: Блок1 Подготовка/Маркетинг/SMM/мониторинг источников; Блок2 Работа с клиентом (воронка, договоры); Блок3 Выполнение работ (реализация); Блок4 Сервис и пост-договор.
  5) Над блоками СТРАТЕГИЯ по сценарному планированию (VUCA): 2–4 сценария будущего + индикаторы + линии действий; гибкая; = системный промпт, относительно неё подбираются источники (агент/человек).
  6) ПЕТРУШКА — непрерывный агент, контекст = ВСЯ система; ежедневный анализ, рекомендации, ведение сценариев/индикаторов.

## 4. Реестр заглушек → решение
- MOCKO (весь сид) → BFF, оставить за флагом DEV_MOCK.
- stub() Раздел не найден → реальные вьюхи.
- petReply() эвристики → orchChat (LLM), эвристика только при !apiMode.
- signals/owlSuggestions из mock → из BFF или удалить.
- TODAY='2026-06-24' хардкод → вычисляемая дата.
- 'Новый пект' (опечатка addProject) → 'Новый проект'.
- Демо-логин Александр/test в index.html → убрать из прода.

## 5. Дорожная карта Этап-1 (вехи)
M1 Де-IoT/терминология ✅ · M2 Устранение заглушек ✅ · M3 Перегруппировка в 4 блока (навигация block:1..4) ✅ · M4 Стратегия-сценарии ✅ · M5 ПЕТРУШКА-непрерывная ✅ · M6 Аудит действий Patch B ✅ · M7 Финучёт/версии артефактов/календарь ✅ · M8 Харднениг ✅ · M9 Замер навыков ✅.

## 6. Известные баги/риски (факт)
- Массовый innerHTML — esc() неединообразно (XSS-риск на реальных данных).
- restore() (localStorage) до loadFromAPI() — приоритет источников не задан (рассинхрон).
- STAGE_MAP из BFF (Проектирование/Выиграна) ≠ фильтры vMetrics (Реализация/Сервис) → конверсия неверна. ~~Частично закрыто M8~~: won→Реализация.
- ~~Ветка master вместо main~~ → ✅ ЗАКРЫТ M8 (2026-07-12).
- ~~IoT-термины в mock (датчики, Телеметрия, фертигиration)~~ → ✅ ЗАКРЫТ M1 (2026-07-12, коммит 530a34fd).
- ✅ api.js: дубли `VERSIONS_READY`/`SKILLS_READY` не обнаружены; отступы и блок feature flags выровнены коммитом 5cd4c8c5 (2026-07-12).
- ~~`#view` не рендерит контент — `bindView()` не был определён~~ → ✅ ЗАКРЫТ issue#1-1 (2026-07-16, коммит `31ca92db`).
- ~~ПЕТРУШКА не отвечала — `owlRender()` и `owlAsk()` не были определены~~ → ✅ ЗАКРЫТ issue#1-2 (2026-07-16, коммит `a63e68c0`).
- ~~seed-данные не загружены в PostgreSQL~~ → ✅ ЗАКРЫТ issue#1-3 (2026-07-17, данные подтверждены Comet: skills:7, scenarios:3, events:5).

## 7. Следующий шаг (ожидает решения пользователя)
**PROD STABLE.** Этап-1 полностью закрыт. Следующий шаг — старт Этапа-2 (M10) по отдельному решению заказчика: реестр источников / монитор мультиопыта / knowledge base / обязательное цитирование / agent_questions.

## 8. Как продолжить в новой сессии
1. Вкладка github.dev: vscode.dev/github/volhover-crypto/agropilot-web (файлы читаются).
2. Быстрое чтение кода: raw.githubusercontent.com/volhover-crypto/agropilot-web/main/js/<файл>.
3. Первое действие: прочитать этот HANDOVER + при необходимости перечитать js/app.objects.js.

## 8a. Продовая архитектура (зафиксировано 2026-07-17)
- **Frontend (static):** `/opt/agropilot-web/` → nginx alias → https://mdked.hlab.kz/agropilot/
- **Backend (FastAPI/uvicorn):** `127.0.0.1:5555`, рабочий systemd-сервис `agropilot-backend.service` (venv: `/opt/agropilot-web/venv/bin/uvicorn`), `enabled` ✅ переживает ребут. ⚠️ Дубль `agropilot.service` (`/usr/local/bin/uvicorn`) ОТКЛЮЧЁН 2026-07-17 (спамил `address already in use`, счётчик рестартов 7696)
- **Database:** PostgreSQL, база `agropilot`, `localhost:5432`, пользователь `postgres`; seed-данные загружены ✅
- **SSL:** Let's Encrypt для `mdked.hlab.kz`; HTTP → HTTPS redirect 302
- **Nginx:** reverse proxy `/agropilot/api` → `127.0.0.1:5555`
- **systemd unit:** `/etc/systemd/system/agropilot.service` — `ExecStart=/usr/local/bin/uvicorn backend.main:app --host 127.0.0.1 --port 5555`, `Restart=on-failure`, `After=postgresql.service`

## 9–13. [см. предыдущие версии HANDOVER — сессии 2026-07-08..16]

## 14. Журнал прогресса (сессия 2026-07-17) — issue#1 ЗАКРЫТ

### Исполнитель: Comet (браузерный агент) + Пользователь (SSH-терминал)

### Шаг 0 — pre-check API (Comet через браузер)
Проверка трёх эндпоинтов до запуска seed:
- `GET /agropilot/api/v1/team/skills` → **skills: 7** ✅
- `GET /agropilot/api/v1/calendar?from=2026-07-01&to=2026-07-31` → **events: 5** ✅
- `GET /agropilot/api/v1/strategy` → **scenarios: 3** ✅

**Вывод:** seed-данные уже были в базе (коммит `c6ec10cc` от 2026-07-16 был применён ранее). Шаги git pull + psql пропущены как избыточные.

### Бонус — systemd (Пользователь в терминале)
- Создан `/etc/systemd/system/agropilot.service`
  - `ExecStart=/usr/local/bin/uvicorn backend.main:app --host 127.0.0.1 --port 5555`
  - `After=network.target postgresql.service`
  - `Restart=on-failure`, `RestartSec=5`
- Выполнено: `daemon-reload → enable → start`
- Статус: `active (running)` ✅
- Проверка: `curl http://127.0.0.1:5555/agropilot/api/v1/strategy` → `ok: true` ✅

### Итог issue#1

| Дефект | Статус | Коммит / Дата |
|---|---|---|
| #1-1 — `#view` / `bindView` | ✅ ЗАКРЫТ | `31ca92db` · 2026-07-16 |
| #1-2 — ПЕТРУШКА / `owlRender`/`owlAsk` | ✅ ЗАКРЫТ | `a63e68c0` · 2026-07-16 |
| #1-3 — seed-данные PostgreSQL | ✅ ЗАКРЫТ | данные подтверждены · 2026-07-17 |
| Бонус — systemd unit | ✅ СОЗДАН | `agropilot.service` · 2026-07-17 |

**issue#1 закрыт пользователем 2026-07-17. Этап-1 завершён полностью.**

### Следующий шаг
Старт Этапа-2 (M10): реестр источников, монитор мультиопыта, knowledge base, обязательное цитирование, agent_questions — по отдельному решению заказчика.

### issue#1-regression — merge conflict в app.objects.js (2026-07-17)

**Симптом:** Alpine init ломался, `#view` пустой — из-за незакрытых conflict-маркеров (`<<<<<<<` / `=======` / `>>>>>>>`) в `js/app.objects.js`. HEAD репозитория содержал обрезанную версию (обрыв на строке 768). Рабочая, полная версия (3673 строки) находилась на диске прода — **диск = источник правды**.

**Действия:**
- Создан бэкап `js/app.objects.js.bak` (untracked).
- Удалены conflict-маркеры, оставлен рабочий код (`const toggleSp` ...).
- `node --check js/app.objects.js` → SYNTAX OK; `grep` маркеров → 0.
- Разрешение выполнено в рамках interactive rebase onto `1a21d0f`: `git add` → `git rebase --continue`.
- `git push --force-with-lease origin main` (история переписана, старый `7e91463` заменён).

**Результат:**
- Новый HEAD: `af17232` (полн. `af172328b92e31e54a1687a1b88a362ad767da0d`)
- Remote `origin/main` подтверждён через `git ls-remote` → `af172328...` = local HEAD.
- Файл: 1 file changed, 2940 insertions(+), 35 deletions(-); маркеры в закоммиченной версии отсутствуют.
- **Статус: ЗАКРЫТ** · 2026-07-17

## 15. Журнал прогресса (сессия 2026-07-17, вечер) — issue#1-regression #2 + Stage-1 backend team/goals

### Исполнитель: Perplexity (аудит + патчи + GitHub) + Пользователь (SSH root@mdked)

### Диагностика (QA-отладчик高level)
Статический аудит prod↔repo (побайтно), карта роутеров, runtime-съём в браузере.
**Root cause:** `vMyDay4()` падал с `Cannot read properties of undefined (reading 'slice')` — BFF-задачи маппились без `date`/`score`, UI звал `t.date.slice(5)`. Исключение убивало `render()` → `#view` пустой (нули + онбординг), клик по «Задачам» тоже не рендерился. Фикс существовал в `b6f3c85a`, но был **потерян при restore `af17232`** (полное восстановление файла затёрло правку).

### Коммиты
| Коммит | Уровень | Что |
|---|---|---|
| `5fa3f87` | P0 фронт | Переприменён `b6f3c85a`: `date: t.due_at` + `score: t.score` в маппинге задач (+2 строки), `node --check` OK, raw-проверка после push |
| `94e1377` | P1 backend | `backend/team/` + `backend/goals/` (models+routes+__init__), регистрация в `main.py`. Паттерн deals: `AsyncSession`, `Depends(get_db/get_current_user)`, конверт `{ok,data}`, `NotFoundError`, read-only Stage-1. `py_compile` OK |

### Деплой (Пользователь, SSH)
- `git pull origin main` → `0753bd9..94e1377` fast-forward
- Обнаружены 4 сервиса agro; порт 5555 держал `agropilot-backend.service` (venv, рабочий), а `agropilot.service` (`/usr/local/bin/uvicorn`) 7696 раз падал `address already in use`
- `systemctl stop + disable agropilot.service` (дубль устранён)
- `systemctl restart agropilot-backend.service` → `active (running)`
- `is-enabled`: `agropilot-backend.service` = **enabled**, `agropilot.service` = **disabled** ✅

### Верификация (публичный домен + браузер, hard-reload)
| Проверка | Было | Стало |
|---|---|---|
| `slice`-ошибка | краш render() | нет |
| Зона 1 «Мой день» | 0/0/0/0 | Просрочено 1 · Горячие 0 · На сегодня 0 · Сделок в работе 8 |
| Онбординг «База пуста» | показывался | заменён реальными данными |
| «Задачи» | рендерил «Мой день» | список из 8 задач |
| «Команда» | 0 человек | 5 человек (U1–U5) с загрузкой |
| `/api/v1/team` | 404 | 200 |
| `/api/v1/goals` | 404 | 200 |

### Статус
**issue#1 ЗАКРЫТ пользователем 2026-07-17** (comment #5005537630 + close). Регрессия #2 устранена, Stage-1 backend team/goals активирован на проде.

### Остаётся вне гейта Этапа-1 (safeLoad-фолбэк, не влияет на рендер)
404 по роадмапу: `/v1/clients` (деривится из deals на фронте), `/v1/health`, `/v1/skills`, `/v1/orchestrator/{digest,recommendations}`, `/v1/packages`, `/v1/artifacts`, `/v1/content`, `/v1/reports`. Кандидаты в Этап-2 (M10).

### Durable-правила (подтверждены этой сессией)
- Полное восстановление файла может затирать точечные фиксы — после restore сверять с последними правками (`b6f3c85a` → потерян в `af17232`).
- Статус Issue проверять в GitHub, а не по markdown HANDOVER.
- На проде рабочий бекенд = `agropilot-backend.service` (venv), НЕ `agropilot.service`.
- Реализация M10 без Computer — по `docs/MAX_AS_COMPUTER.md` (режим Max-as-Computer: contract-first, verify после каждого шага, мультимодельное ревью).

> **2026-07-18:** ТЗ Этап-2 зафиксировано в `docs/TZ_STAGE2.md`; работаем 1 шаг = 1 тред (`docs/PROMPT_STEP_TEMPLATE.md`); без Issues.
> **2026-07-18:** Issues #2–#10 и Milestone «M10 — Этап-2» закрыты как superseded; трекинг Этапа-2 — `docs/TZ_STAGE2.md` + `HANDOVER.md`.

> **2026-07-19: Блок E (Stage 2) — RBAC PATCH /team/{member_id} задеплоен.**
> commit `1553719` feat(stage2/E): RBAC PATCH /team/{member_id}, models+routes (§11).
> - models.py: +competencies/permissions(JSONB)/status/role_key + to_dict; id→String(16); dead import Any удалён.
> - routes.py: +TeamPatch, +_is_manager (role_key∈{manager,admin}), +PATCH /{member_id} с ForbiddenError-гейтом (whitelist, exclude_unset).
> - push b11e196..1553719; raw-verify ForbiddenError OK; restart active; smoke GET /team = 200.
> - gate-логика _is_manager корректна; E2E негативный тест (403) невозможен — get_current_user = STUB (всегда U1/manager).
> - **Stage 3 блокер (prod-security):** заменить STUB на реальный JWT в backend/common/deps.py до продакшн-релиза RBAC.
> - Техдолг: _is_manager делает доп. db.get по user.id (избыточно при JWT с role_key в payload); enum-валидация status/role_key в PATCH отсутствует.

> **2026-07-19: M10-2 Sources — CRUD /sources задеплоен.**
> commit `b25e3c6` feat(M10-2): sources CRUD — GET/POST/PATCH/DELETE /sources, migration 005, VALID_TYPES guard.
> - migration 005_sources.sql: CREATE TABLE sources (id SERIAL PK, type VARCHAR(16) CHECK IN(site/rss/telegram/tender), url, handle, keywords JSONB, active BOOL, created_at TIMESTAMPTZ).
> - models.py: Source ORM + to_dict().
> - routes.py: GET(filter active/limit) / POST / PATCH / DELETE, VALID_TYPES 422-guard, NotFoundError, конверт {ok,data}.
> - main.py: +import sources_router + include_router /agropilot/api/v1.
> - raw-verify VALID_TYPES OK; restart active; smoke GET /sources = 200 {"ok":true,"data":[]}.
> - RBAC нет (любой авторизованный); техдолг: общий Base, enum-валидация через app (есть) и DB CHECK (есть).
> - Следующий блок: M10-3 /content.

> **2026-07-19: Техдолг — sources vs TZ_STAGE2.md (Блок D).**
> Реализованный /v1/sources (commit b25e3c6) — упрощённый MVP: type=site/rss/telegram/tender, без полей linked_strategy_task/added_by/status=proposed.
> По TZ_STAGE2.md §5.3 (Блок D) финальная схема sources: type=news/supplier/competitor/market/tech, +linked_strategy_task, +added_by, +status (active/proposed/disabled/rejected), +receiver_user_id, +routing_reason.
> Расширение sources до полной Блок-D схемы — отдельный шаг ПОСЛЕ реализации Блока C (стратег.задачи) и Блока E (RBAC).
> Текущий /v1/sources работает как scaffold — не ломает прод, расширяется миграцией.

> **2026-07-19: M10-3 Content — CRUD /content задеплоен.**
> commit `b75ab70` feat(M10-3): content CRUD — GET/POST/PATCH/DELETE /content, migration 006, VALID_PLATFORMS/STATUSES guard, auto published_at.
> - migration 006_content.sql: CREATE TABLE content (id SERIAL PK, title, body, platform VARCHAR(32) CHECK IN(telegram/instagram/vk/linkedin/other), status VARCHAR(16) CHECK IN(draft/published/archived) DEFAULT draft, author_id→team(id) FK ON DELETE SET NULL, published_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT now()).
> - models.py: Content ORM + to_dict().
> - routes.py: GET(platform/status/limit) / POST / PATCH / DELETE, VALID_PLATFORMS/VALID_STATUSES 422-guards, NotFoundError, auto published_at=now() при PATCH status=published.
> - raw-verify VALID_PLATFORMS OK; restart active; smoke GET /content = 200 {"ok":true,"data":[]}.
> - RBAC нет (любой авторизованный); техдолг: общий Base.
> - Следующий блок: M10-4 /packages.

> **2026-07-20: M10-4 Packages — CRUD /packages задеплоен.**
> commit `6ed666b` feat(M10-4): packages CRUD — GET/POST/PATCH/DELETE /packages, migration 007, VALID_STATUSES guard.
> - migration 007_packages.sql: CREATE TABLE packages (id SERIAL PK, title VARCHAR(300), description TEXT, price NUMERIC(12,2), status VARCHAR(16) CHECK IN(draft/active/archived) DEFAULT draft, deal_id→deals(id) FK ON DELETE SET NULL, created_at TIMESTAMPTZ DEFAULT now()).
> - models.py: Package ORM + to_dict() (price → float).
> - routes.py: GET(status/deal_id/limit) / POST / PATCH / DELETE, VALID_STATUSES 422-guard, NotFoundError, конверт {ok,data}.
> - raw-verify VALID_STATUSES OK; restart active; smoke GET /packages = 200 {"ok":true,"data":[]}.
> - RBAC нет (любой авторизованный).
> - Следующий блок: M10-5 (уточнить по ROADMAP_M10.md).

> **2026-07-20: M10-5 Artifacts — CRUD /artifacts задеплоен.**
> commit `98edecc` feat(M10-5): artifacts CRUD — GET/POST/PATCH/DELETE /artifacts, migration 008, VALID_KINDS guard, FK на уровне БД.
> - migration 008_artifacts.sql: CREATE TABLE artifacts (id SERIAL PK, kind VARCHAR(32) CHECK IN(kp/contract/schema/other), title VARCHAR(300), url TEXT, deal_id VARCHAR(16) FK→deals(id) ON DELETE SET NULL, created_at TIMESTAMPTZ DEFAULT now()).
> - models.py: Artifact ORM, локальный Base(DeclarativeBase), to_dict(), deal_id БЕЗ ORM-ForeignKey (FK только в миграции на уровне БД).
> - routes.py: GET(kind/deal_id/limit) / POST / PATCH / DELETE, VALID_KINDS 422-guard (в POST и PATCH), NotFoundError→404, конверт {ok,data}.
> - main.py: +import (стр.21) router as artifacts_router + include_router (стр.69) /agropilot/api/v1.
> - Полный CRUD-smoke: POST/GET/PATCH/DELETE + guard'ы + DELETE 9999→404 OK. raw-verify маркеров OK; restart active; smoke GET /artifacts = 200 {"ok":true,"data":[]}.
> - RBAC нет (любой авторизованный).
> - ПРОТОКОЛ: исходный контракт M10-5 содержал 4 дефекта, устранены при деплое. ЭТАЛОН для новых модулей = backend/packages (M10-4), НЕ artifacts-контракт:
>   1) python -> python3 (нет алиаса на сервере).
>   2) импорты: backend.common.deps (get_db, get_current_user) + backend.common.errors (NotFoundError), НЕ backend.database/auth/errors.
>   3) сериализация: метод to_dict(), НЕ obj.__dict__ (иначе 500 на _sa_instance_state).
>   4) модель: локальный Base(DeclarativeBase), БЕЗ ORM-ForeignKey (иначе NoReferencedTableError на commit); FK только в миграции.
> - Регрессия M10-4 packages проверена LIVE POST → багов нет (packages написан по эталону изначально).
> - Следующий блок: M10-1 Clients (по порядку ROADMAP: sources→content→packages→artifacts→clients).

## Context Guard — 2026-07-21

`CG-20260721-01 | Блок E: пользователи / компетенции / права | docs/TZ_STAGE2.md §5.1 + CONTRACTS.md §11 | drift caught YES | rework NO | PASS`

- ШАГ D-1 завершён PASS: аудит `owlContext()` выполнен read-only, gap-отчёт утверждён Оркестратором.
- ШАГ-0-E обнаружил, что Блок E уже реализован коммитом `1553719` и закрыт HANDOVER-коммитом `99075c9`.
- Проверены модель, маршруты, миграция `004_team_rbac.sql`, схема `public.team` и `GET /agropilot/api/v1/team`.
- Повторная реализация E предотвращена; backend-изменения и новые миграции не требуются.
- `USERS_READY` остаётся `false`; frontend Блока E не включался.
- Документационное замечание: CONTRACTS.md называет `status`/`role_key` типом TEXT, фактически используются VARCHAR(16)/VARCHAR(32).
- Следующая точка по утверждённому порядку Этапа-2: Context Guard перед Блоком C.


> **2026-07-22 (процессное правило):** Контракты и docs правятся стандартным
> циклом: правка файла → git diff → «ОК» → commit → push → raw-verify по full
> SHA. Промежуточные payload-файлы, манифесты, Base64-транспорт и DRY-RUN-замены
> НЕ используются. Контракт, не закоммиченный в repo, считается несуществующим.

## Блок C (strategy_tasks) — прогресс 2026-07-22/23

> **2026-07-22, backend (8b8a5d8cae860f32f7ef1df1afca15e7153398a0):** миграция
> 010_strategy_tasks.sql + backend/strategy_tasks/ (models, routes по эталону
> backend/packages) + регистрация в main.py. Smoke 200 {ok,data} на проде.
> Верификация: raw-verify Ревизора (состав коммита, py_compile) — PASS.

> **2026-07-23, frontend §12.5 (8da69bf17c8d21faaece8cbfff64c6cba8ab3699):**
> js/api.js — STRATEGY_TASKS_READY:true + 4 CRUD-метода /v1/strategy/tasks;
> js/app.objects.js — M.strategyTasks в цепочке loadFromAPI (порядок по контракту).
> repo==prod байт-сверкой (api.js 10865 B), visual smoke PASS.
> Верификация: независимо Архитектор (raw@SHA сам) и Ревизор — оба PASS.
> Осталось по §12: owlContext §12.6 → DoD §12.8.

> **2026-07-23, owlContext §12.6 (6d872db4a1d6563228e4f3165de48d5b8da7c8ce):**
> js/app.objects.js — owlContext() дополнена полем strategyTasks: активные
> задачи (status='active') нормализуются до {id,title,owner_id,monitoring_focus,
> linked_scenario,priority,status}; monitoring_focus→[] фолбэк; хелпер withST(o)
> подмешивает поле во ВСЕ 6 веток возврата (all + goal/project/client/deal/task).
> owlContextDealIds() не тронут. node --check OK. repo==prod (264974 B).
> Верификация: Архитектор raw@6d872db сам — PASS; visual smoke на проде — PASS.
> Известные хвосты: двойной init()/loadFromAPI в консоли (не влияет на данные);
> mock.objects.js без поля strategyTasks (в mock-режиме массив пуст — корректно).

## Блок C (strategy_tasks) — ПРИНЯТ 2026-07-23

> DoD §12.8 — приёмка Архитектора:
> [PASS] #1 миграция 010_strategy_tasks, strategy не изменена (8b8a5d8)
> [PASS] #2 CRUD /v1/strategy/tasks {ok,data}, smoke 200 (8b8a5d8)
> [PASS] #4 frontend M.strategyTasks, без подмены M.tasks/M.strategy (8da69bf)
> [PASS] #5 owlContext active-only + monitoring_focus (6d872db)
> [PASS] #7 git diff --check=0, регистрация router, /v1/strategy и
>        route/object-контекст без регрессий
> [ПРИНЯТО С ОГОВОРКОЙ] #3 RBAC: enforce на запись = dev-fallback STUB
>        (get_current_user без role_key); manager/admin-контроль активируется
>        с реальным JWT — известный Stage-3 blocker (см. Блок E).
> [ТЕХДОЛГ] #6 автотесты (pytest CRUD/401/403/404/validation/active-inactive
>        + frontend smoke) НЕ написаны; только ручная верификация.

## ТЕХДОЛГ Этапа-2

> - #6 §12.8: автотесты strategy_tasks (pytest по эталону backend/packages).
> - Двойной init()/loadFromAPI/Splitter в консоли прода — двойная инициализация
>   Alpine; на данные/функциональность не влияет, требует разбора.
> - mock.objects.js: добавить strategyTasks: [] для полноты mock-модели.
> - RBAC strategy_tasks enforce — со Stage-3 JWT.

## Блок E-seed — ПРИНЯТ 2026-07-23

> 011_team_competencies_seed.sql (43817f27e1675ae64ea9f24792ad57693a89c97d):
> идемпотентное наполнение team.competencies[] по role_key.
> manager(U1,U2)=[стратегия,клиенты,сделки]; engineer(U3,U5)=[поставщики
> оборудования,агротех,сопредельные рынки]; smm(U4)=[агро-инфополе,соцсети,контент].
> Применено: UPDATE 2/2/1. Верификация: Архитектор raw@full SHA сам + psql SELECT — PASS.
> Предусловие маршрутизации proposed (Блок D D-5.2/D-5.3) выполнено.

## Блок D (sources revision + proposed routing) — ПРИНЯТ 2026-07-24

> **2026-07-24, миграция K1 (955f753f):** 012_sources_revision.sql —
> ревизия таблицы sources: CHECK type-набор ТЗ (news/supplier/competitor/market/tech),
> status/routing/FK (status VARCHAR(16) DEFAULT 'active', linked_strategy_task,
> added_by, receiver_user_id, routing_reason). Таблица была пуста — без потери данных.

> **2026-07-24, backend K2 (5f4f6486):** sources backend — VALID_TYPES ТЗ, RBAC
> (_is_manager()), D-5 routing (added_by→receiver/competency), approve/reject
> эндпоинты, 3 новых поля. Эталон backend/packages, протокол 4 дефектов соблюдён.

> **2026-07-24, frontend K3 (94f9bdb3):** js/api.js — SOURCES_READY:true,
> loadSources/createSource/updateSource/approveSource/rejectSource;
> app.objects.js — M.sources в _loadAllData(), owlContext activeSources+strategy.

> **2026-07-24, vMyDay4 K4 (4864137):** app.objects.js — виджет «Предложения
> на мониторинг» зона 5: sources status='proposed' с receiver_user_id==me(U1 stub
> до JWT); кнопки Одобрить/Отклонить. §13.7 выполнен.

> DoD §13.9 — приёмка Архитектора:
> [PASS] #1 owlContext activeSources+strategy — K3 (94f9bdb3)
> [PASS] #2 /v1/sources типы news/supplier/competitor/market/tech — K2 (5f4f6486)
> [PASS] #3 ПЕТРУШКА POST status=proposed — K2 (5f4f6486)
> [PASS] #4 proposed → «Мой день» receiver_user_id + approve/reject — K2+K4
> [PASS] #5 миграция без потери строк, git diff --check=0, router зарегистрирован
> [ПРИНЯТО С ОГОВОРКОЙ] RBAC: me=U1 stub до JWT (Stage-3 blocker, Блок E)
> HEAD на момент приёмки: 48641374863b5fa0058e9175825bf97725cac429

## Процессный запрет Архитектору — 2026-07-24

> Зафиксировано по прямому указанию Оркестратора.
> Архитектору ЗАПРЕЩЕНО: браузерный режим «Компьютер»/Comet, запуск субагентов,
> декомпозиция шага на параллельные задачи, загрузка исполнительских skill (coding и т.п.),
> создание отдельного managed-clone/worktree помимо согласованного КАНАЛА ЧТЕНИЯ.
> Архитектор — read-only ревьюер: чтение repo/прода только через код-песочницу (urllib) по SHA.
> Записи в repo делает ТОЛЬКО Кодер (или Ревизор при эскалации). Один шаг = один verbatim-блок Кодеру, затем СТОП.

## 2026-07-24 — Блок C фронт-хвост закрыт: вью-раздел «Стратегия» (§12.9)

Сделано (commit 81151b0, "feat(frontend): strategy view (vStrategy) + contract 12.9"):
- CONTRACTS.md §12.9 «Вью-раздел Стратегия» (конец блока C; §12.6 «Контекст ПЕТРУШКИ» не тронут).
- js/api.js:328 STRATEGY_VIEW_READY: true (рядом с STRATEGY_TASKS_READY:327).
- js/app.objects.js:473 ветка else if (this.route === 'strategy') html = this.vStrategy();
  метод vStrategy() (стр.3678) — read-only по this.M.strategyTasks, без новых fetch;
  карточки title/priority(pill)/monitoring_focus[](теги) + пустое состояние
  «Стратегических задач пока нет».

Верификация Архитектора: raw@81151b0 прочитан построчно — PASS (3 файла, 53 insertions,
0 deletions, границы §12.5/§12.6/backend соблюдены).
Визуальный smoke: #/strategy рендерит пустое состояние, заглушка «Раздел не найден» ушла,
консоль без красных ошибок JS — PASS. Рестарт backend не требовался (чистый frontend).

Открытый хвост Блока C: CRUD-UI создания стратегических задач в #/strategy
(кнопка «создать» + форма поверх готового createStrategyTask) — отдельным шагом.

Следующий по §7: Шаг 2 — Блок E (справочник пользователей/компетенций/прав через
расширение team), до Блока D (требование §9: E раньше D для адресности
proposed).

## 2026-07-24 — Блок E ЗАКРЫТ: RBAC (backend + фронт §12.10 + маппинг)

Коммиты: e36f7b0 (RBAC-редактор §12.10, детектор mgr по role_key),
         e86a0a7 (fix маппера M.team: role_key/competencies/permissions/status).

Верификация Архитектора (raw@e86a0a7 + прод): PASS. Визуальный smoke «Команда»: RBAC-поля
рендерятся значениями, форма редактора у менеджера работает (PATCH 200, status сохранён),
не-менеджер read-only, backend-гейт _is_manager держит (curl без сессии → 403). DoD E п.3
(права реально ограничивают) подтверждён.

Инцидент smoke: при сохранении форма шлёт role_key целиком → менеджер понизил себя до member,
форма пропала. Восстановлено разовым SQL: UPDATE team SET role_key='manager' WHERE id='U1'
(U1 Екатерина). Сейчас менеджеров 2: U1 Екатерина, U2 Оксана.

БЭКЛОГ (UX, не DoD): предохранитель формы RBAC — role_key по умолчанию = текущее значение
члена + confirm() при самопонижении. Отдельным мелким шагом.

Статус Этапа-2: C закрыт (§12.9). E закрыт (backend RBAC + §12.10 + маппинг). D backend закрыт
(_route_proposed D-5, approve/reject) + фронт vMyDay4.
ОСТАЁТСЯ: Блок A (7 разделов «полноценно» + /v1/clients вместо derive), Блок B («Справочник»
tree /v1/catalog), сквозной smoke D-5 (proposed→approve→owlContext) с наполнением данных,
хвост C (CRUD-UI создания стратег.задач).

### 2026-07-24 — §12.12 форма «+ Источник» пишет в backend (DONE)
Контракт: 8a144acffd4b82b617be7355afb3c878de7776d8 (CONTRACTS.md §12.12)
Код:      79c4a1236b3a1ccde19ad27c1ee6691e314e5d57 (js/app.objects.js, srcAddModal)
Суть: форма делала mock this.M.sources.push(value/scope/industry) — источник пропадал
после перезагрузки. Теперь POST /v1/sources через window.AGL.createSource:
{type,url,handle||null,keywords[],status:'active'}. added_by НЕ шлём с фронта —
проставляет backend (_route_source, D-5). Успех -> loadSources()+render()+toast.
Ошибка/сеть -> toast, форма не падает.
Приёмка: node --check CHECK_OK; raw-verify обоих SHA Архитектором PASS;
UI-smoke persist после Ctrl+Shift+R — PASS; консоль без ошибок по sources.
Известный фон (не регресс): 404 на /v1/reports и /v1/orchestrator/* — роутеров нет в
backend/, safeLoad отдаёт fallback штатно.
Не тронуты: vMonitoring §12.11, блок сигналов, scan/toggle, backend.

### 2026-07-26 — A-6 «Входящие клиенты» /v1/clients (DONE, CLIENTS_READY=true)
Контракт: 98b5d961af50bd323eb3f72449b587569889f628 (CONTRACTS.md §13.1)
Backend:  3e22a6bd3d915e1d239df201cb60574787d634f7 (backend/clients/*, main.py,
          migrations/013_clients_api.sql)
Frontend: 0ab355dacb014391d2eb08d2b7b112ba86ef1579 (js/api.js loadClients ->
          safeLoad('/v1/clients?limit=100'), дерив из deals удалён)

ФАКТ, найденный при recon: таблица clients УЖЕ существовала (создана ранним
seed_prod.sql, вне backend/migrations), 5 записей C1-C5, живой FK
deals.client_id -> clients(id), 8 сделок ссылаются. Исходный план с CREATE TABLE
и backfill отменён — пересоздание разрушило бы FK. Сделан API-слой поверх неё.

Миграция 013_clients_api.sql — идемпотентная, ADD-only:
  +source varchar(32), +status varchar(16) default 'active',
  +created_at timestamptz default now(); затем UPDATE ... WHERE IS NULL.
  Факт применения: ALTER x3, UPDATE 0 (status уже был) / 5 (source был NULL) /
  0 (health уже заполнен). Бэкап до ALTER: /tmp/clients_backup_20260726_175325.sql
  Колонка deals_count НЕ трогалась и НЕ читается API — она разошлась с фактом.

API: GET /clients (?status=&health=&limit=), GET /clients/{id}, POST, PATCH,
контракт {ok,data}. dealsCount считается агрегатом из deals
(select client_id, count() group_by) — не из колонки deals_count.
VALID_HEALTH={green,yellow,red}, VALID_STATUS={active,inactive,archived},
VALID_SOURCE={manual,signal,smm,petrushka}, невалидное -> 422.

Приёмка (пруфы получены): py_compile COMPILE_OK; node --check CHECK_OK;
raw-verify всех трёх SHA Архитектором PASS; \d clients — новые колонки есть,
PK/FK целы; POST без id -> автоген C6, 200; health='purple' -> 422 (не 500);
PATCH C6 health -> red, 200; GET -> 6 записей, dealsCount C1..C3=2, C4/C5=1, C6=0;
UI «Клиенты · 6», индикатор шапки API (не Demo), health-точки и dealsCount верны;
регресс deals/sources/team/goals = 200.
Тестовый C6 удалён после приёмки: guard deals WHERE client_id='C6' = 0,
DELETE 1, итог cnt=5 (C1-C5).

Не тронуты: deals, sources, RBAC, seed_prod.sql, колонка deals_count, FK,
js/app.objects.js (он уже маппил {id,name,industry,region,need,health,dealsCount}).

СЛЕДУЮЩЕЕ (не начато):
- A-6.1 импорт базы Bitrix24: файл contacts_bitrix24.csv, 1491 строка, 938 с компанией
  (916 уникальных), формы КФХ 435 / ООО 281 / ИП 41 / АО 21 / СПК 19; region и industry
  в выгрузке ОТСУТСТВУЮТ; 454 записи — недозвон/отказ/не ЦА; телефон у 1423, email у 157.
  Требует отдельный контракт §13.2: +phone/+email/+contact_person/+owner/+ext_id,
  префикс id, дедуп по названию, фильтр мусора, пагинация UI, решение «клиент vs лид».
- Далее по §7 Блок A: deals -> content -> monitoring -> goals/context/strategy.

## A-6.1 «Лиды» + импорт Bitrix24 — DONE (2026-07-26)

Контракт: CONTRACTS.md §14. Флаг: LEADS_READY = true.

Цепочка коммитов:
- 9a418b4a1d179b056ca19642c104463d57f1ec04 — docs(contract): 14 leads + bitrix24 import
- 8d874c8cb8719f33262d341509504e8e8455a75f — chore(seed): bitrix24 leads import fragments (916 rows)
- 800eb307f8c14934d61bec789a758dbde009f514 — docs(contract): fix 14 phone counts to actual
- 288e97155ca38eaa95917b190810460adbf8097c — feat(backend): leads router + 014 migration
- 424ccc84d6fc0ece551e1950f03a84875aefac3b — feat(frontend): leads section with pagination

Факты БД (после импорта):
- leads = 916; active 223 / inactive 693; phone IS NOT NULL = 909
- phone_extra у 246 записей, 357 доп. номеров; 909 + 357 = 1266 — сходится с §14
- source = 'bitrix24' у всех 916; clients = 5, не изменялись
- FK leads_converted_client_id_fkey -> clients(id) ON DELETE SET NULL;
  индексы leads_status_idx, leads_ext_id_idx
- Миграция 014_leads.sql идемпотентна (CREATE TABLE/INDEX IF NOT EXISTS);
  seed идемпотентен (ON CONFLICT (id) DO NOTHING)

API (curl 127.0.0.1:5555):
- GET /v1/leads -> {ok,data:{items,total,limit,offset}}, total 916, limit le=200
- ?status=active -> 223; ?status=bogus -> 422 VALIDATION_ERROR (не 500)
- ?q= ILIKE по name/contact_person/phone; кириллица работает (q=вино -> 29)
- offset=915 -> B916; GET /leads/{id} -> 404 на отсутствующий
- PATCH /leads/{id} и POST /leads/{id}/convert реализованы (convert из UI пока недоступен)
- Регресс: /clients, /deals, /sources = 200

Frontend: раздел «Лиды» (index.html стр. 120, Блок 2), vLeads() с пагинацией,
фильтром по статусу и поиском; обработчики через data-lead-status /
data-lead-page / #leadSearch в bindView(). UI проверен Оркестратором (Ctrl+Shift+R).

Уроки процесса:
- Пересказ исполнителя != пруф: дважды подвёл (эмодзи навигации — реально 🏢, не 👥;
  «артефакт ввода» вместо диагностики поиска). Принимать только вывод команд.
- Python-патчи по якорям обязаны содержать assert: ветка else без изменения строки
  дала ложноположительный «patched» при нетронутом файле.
- Признак деградации сессии Кодера: два и более ответа «сейчас выполню» без вывода
  команд, самовольные тестовые плейсхолдеры. Лечится новой сессией, не переспросом.
- Канал чтения GitHub из песочницы Архитектора недоступен (TLS unexpected eof,
  проверено ~12 раз разными транспортами). Raw-verify выполнялся через
  `git show origin/main:<path>` силами Кодера.

Следующее: CONTRACTS.md §15 (A-6.1 UX v2), SHA 377a90275945f700503d6592e51d189802a95c3b,
прочитан и принят Архитектором. Дефект §15.1: пример ответа /leads/stats записан без
обёртки data и с лишней скобкой — реализуем по §15.5 ({ok,data:{...}}), текст §15.1
поправить отдельным docs-коммитом.

---

## Запись 2026-08-25 — §15.6/§15.7 реализованы (лиды, механики Битрикс24)

Контракт `9c14065` (26.07) реализован. Коммиты, в порядке применения:

| SHA | Что |
|---|---|
| `bd48c48` | миграция `015_leads_next_action.sql` — `next_action text`, `next_action_at date`, индекс; без FK |
| `30d4c39` | ORM-модель `Lead`: два поля + `to_dict()` |
| `9d07fe0` | `backend/leads/routes.py`: §15.7 A/B/C/D |
| `b80b2a4` | `js/api.js` + `js/app.objects.js`: создание, «Некачественный», convert с выбором, колонка «Дело до» |

DoD отмечен в CONTRACTS.md полностью. Где что проверялось:

- **На проде** (после `systemctl restart agropilot-backend`, 22:11): создан `B917`,
  виден в списке; `PATCH` в `inactive` без comment -> 422, с comment -> 200;
  `convert?target=client_deal` -> клиент `C6` + сделка `D9` (`stage=lead`,
  суммы/даты пустые); повторный convert -> 409; пустой/отсутствующий `name` -> 422;
  `sort=bogus`, `target=bogus` -> 422; дефолт списка `name asc` не изменился;
  регресс leads/clients/deals/sources/strategy/tasks/team/goals = 200; сайт 200.
- **На изолированной БД** `agropilot_test` (временный uvicorn :5556, БД удалена):
  весь DoD целиком, включая `target=client` (дефолтная ветка §14) — на проде
  эта ветка намеренно не выполнялась, чтобы не плодить лишних клиентов.
- UI: раздел «Лиды» рендерит, обе модалки открываются и блокируют пустое
  обязательное поле; в консоли ошибок от лидов нет.

**Тестовые артефакты на проде** (помечены в названии, удалять SQL-ом вручную):
лид `B917`, клиент `C6`, сделка `D9` — «ТЕСТ §15.7 приёмка — можно удалить».

### Решения и открытые вопросы

1. **`stage` новой сделки = `lead`.** §15.7 B требует «первый из существующего
   `VALID_STATUS` deals», но такого набора в `backend/deals` нет: поле называется
   `stage`, валидации значений нет вообще (`PATCH /deals` принимает любую строку).
   Взят `default` модели `Deal`. Согласовано 2026-08-25. Отдельный вопрос —
   нужен ли `VALID_STATUS` в deals — требует своего контракта.
2. **P1 наполовину инертен.** Колонка «Дело до», сортировка `sort=next_action_at`
   и подсветка просроченных сделаны. Но **задать** `next_action` нечем: §15.7 C
   правит в PATCH только правило про `comment`, список полей `LeadPatch` идёт из
   §14, где этих полей нет. Нужна поправка контракта (§15.8) на добавление
   `next_action`/`next_action_at` в `PATCH /v1/leads/{id}` — без неё поля
   заполняются только SQL-ом.
3. **Кнопка «Открыть» у лида мертва.** `data-lead-open` не имеет обработчика в
   `bindView()`; карточки лида (§15.2) в коде нет. Дефект существовал до этой
   задачи, в §15.6/15.7 не входит.

### Зафиксированные факты по инфраструктуре (закрывают старые расхождения)

- **127.0.0.1:5555 держит `agropilot-backend.service`** (venv,
  `/opt/agropilot-web/venv/bin/uvicorn backend.main:app`). Проверено по
  cgroup процесса. `agropilot.service` — masked + inactive. Запись HANDOVER
  от 17.07, называвшая рабочим `agropilot.service`, **неверна**.
- **`tg_ingest.py` не трогает `leads`/`clients`** — единственный SQL-доступ во
  всех 280 строках это `INSERT INTO agropilot.reports`. Изменения схемы лидов
  для ingest безопасны.
- **Статика раздаётся напрямую из `/opt/agropilot-web/`**, без сборки: любая
  правка `js/` становится живой на сайте немедленно, до рестарта бэкенда.
  Порядок работ: сначала бэкенд + рестарт, только потом фронт. В этой задаче
  порядок был нарушен — между записью `js/` и рестартом кнопка «Создать лид»
  на проде отдавала 405. Данные не пострадали.
- Миграции применяются вручную (`psql -f`), таблицы учёта и раннера нет.
- Дефект аудита `AgroPILOT_Audit_and_ClaudeCode_Instruction.md`: он называет
  HEAD `9c14065` и утверждает, что кода после него не было. Фактически после
  него были `3a17f51` и `df2c8f4`.

### Следующее по приоритету

1. A-3 Мониторинг — единственный раздел Блока A без backend-роутера; нужен контракт.
2. Рассинхрон `CLIENTS_READY`/`CONTENT_READY`: флагов в `js/api.js` нет, HANDOVER
   заявляет `CLIENTS_READY=true`. Решить — добавить флаг или закрыть записью.
3. Блок B «Справочник» (tree-view) — только после A-3.

## Запись 2026-08-25 (продолжение) — §15.8 и синхронизация с GitHub

**§15.8 «Дело по лиду на запись»** — контракт `67bd264`, реализация `fa814c3`.
DoD отмечен полностью, проверялся на проде после рестарта (MainPID 3791298):
PATCH с делом -> 200 и поля в ответе; `next_action_at='2026-13-45'` -> 422 без
500; явный null очищает оба поля; §15.7 C не сломан (inactive без comment -> 422);
`sort=next_action_at` раскладывает по сроку, NULL в конце; в UI просроченный
срок красный (`rgb(239,68,68)` = `var(--err)`) с маркером «!», будущий обычный;
модалка «Дело» предзаполняется текущими значениями, пустая форма очищает —
проверено сквозняком через UI до записи в БД и обратно.

Тестовые «дела» проставлены на проде: B2 (10.09), B3 (01.08, просрочено);
B1 и B4 очищены после проверки очистки.

### GitHub: пуш восстановлен без нового токена

Пуш падал с `Invalid username or token`. Причина — **в git remote был вшит
мёртвый PAT**, который перебивал уже настроенный credential helper. На хосте
есть авторизованный `gh` (аккаунт volhover-crypto, push:true), а git настроен
на `credential.https://github.com.helper = !/usr/bin/gh auth git-credential`.

Исправление — одна команда, новых секретов не заводили:

    git remote set-url origin https://github.com/volhover-crypto/agropilot-web.git

Теперь аутентификация идёт через gh. Побочно закрыто требование «не хранить
токен в URL remote»: в конфиге его больше нет.

origin/main = `fa814c3`, рабочее дерево прода чисто, расхождений нет.

**Поправка к предыдущим записям.** Формулировка «da9ea1e/df2c8f4/3a17f51 не
уехали на GitHub» неверна — она была сделана по устаревшему remote-tracking
ref (на проде долго не делали `git fetch`). Фактически GitHub уже содержал
`da9ea1e`; новыми были только 7 коммитов этой сессии. Расхождение аудита
(HEAD `9c14065`) и брифа (HEAD `da9ea1e`) объясняется временем чтения:
`da9ea1e` закоммичен 25.08 в 18:46, аудит читал репозиторий раньше.

### Оставшиеся висящие контракты (не входили в эту задачу)

- **§15.1a** (26.07, `3a17f51`) — границы строк и ресайз колонок таблицы лидов.
  НЕ реализован: `#leadsTable` в коде отсутствует, DoD пуст. Найденные в
  index.html `col-resize` относятся к резайзеру панелей, не к таблице.
- **Кандидат на новый контракт:** `PATCH /v1/deals` принимает любую строку в
  `stage` без валидации — та самая дыра, из-за которой §15.7 B ссылался на
  несуществующий `VALID_STATUS` в deals. Живые значения: lead, assess,
  proposal, deal.
- A-3 Мониторинг, рассинхрон `CLIENTS_READY`/`CONTENT_READY`, Блок B —
  без изменений, см. предыдущую запись.

## Запись 2026-08-25 (продолжение 2) — §16 валидация стадий сделок

Контракт `da31249`, реализация `5984198`. DoD отмечен полностью, проверка на
проде после рестарта (MainPID 3814209).

Что было: `PATCH /v1/deals/{id}` писал в `stage` любую строку — ни словаря, ни
проверки. Опечатка выбрасывала сделку из воронки (фронт группирует по известным
кодам) и из фильтра `GET ?stage=`, причём фильтр по несуществующему коду отдавал
пустой список, неотличимый от «сделок нет». Это же отсутствие набора вынудило
§15.7 B ссылаться на несуществующий `VALID_STATUS deals`.

Что стало: `VALID_STAGES` в `backend/deals/models.py` — 8 кодов в порядке
воронки, взяты из `STAGE_MAP` (js/app.objects.js:121), новых не вводилось.
`_validate_stage()` применён к `PATCH` и к фильтру `GET`. В leads литерал
`DEAL_INITIAL_STAGE = "lead"` заменён на `VALID_STAGES[0]` — значение прежнее,
§15.7 B не изменился, ушло дублирование и комментарий «набора нет».

Проверено на проде: `stage=bogus` -> 422 с перечнем допустимых, и в PATCH, и в
GET; все 8 кодов принимаются (прогнаны по очереди на D9, стадия возвращена в
lead); `?stage=lead` фильтрует; исходные D1-D8 не изменились (assess 2,
proposal 2, deal 1, lead 3); `convert?target=client_deal` создал D10 со стадией
lead; регресс 8 эндпоинтов и сайт = 200; раздел «Сделки» рендерит, воронка
показывает «Зацепка · 5».

Схема БД не менялась. CHECK-констрейнт на `deals.stage` намеренно не добавлен
(§16 E): в ту же базу пишут внешние процессы, отказ на уровне БД уронил бы их
вставки. Валидация только на уровне API.

### Известное, но не сделанное (зафиксировано в границах §16 F)

- Допустимость ПЕРЕХОДОВ между стадиями не проверяется: любая стадия может
  смениться на любую. Нужен отдельный контракт, если требуется воронка с
  односторонним движением.
- Карта `REV` во фронте продублирована: js/app.objects.js:1781 и :1795.
  Расхождение копий даст трудноуловимый баг. Чистка фронта, отдельной задачей.

### Тестовые артефакты на проде (накопились, удалять одним скриптом)

Лиды `B917`, `B918`; клиенты `C6`, `C7`; сделки `D9`, `D10` — все содержат
«ТЕСТ §15.7» / «ТЕСТ §16» в названии. Плюс «дела» на B2 (10.09) и B3 (01.08).
Скрипт удаления не выполнялся — по договорённости чистим в конце разработки.

## Запись 2026-08-25 (продолжение 3) — §15.1a таблица «Лиды»

Правка контракта `80b9f68`, реализация `d5321a6`. §15.1a лежал нереализованным
с 26.07. DoD отмечен полностью, проверка в живом UI.

Правка контракта понадобилась до кода: §15.1a перечислял семь колонок с
ширинами, а §15.6 п.4 добавил восьмую («Дело до»). Зафиксированы её ширина
(120px), ключи колонок в localStorage и снятие `max-w-[180px]` с ячеек — при
`table-layout: fixed` ширину задаёт `<colgroup>`, и без снятия ресайз шире
180px не давал бы видимого эффекта.

Проверено в браузере (значения — из computed styles, не на глаз):
- границы: `td` 1px по низу и справа, у последней колонки правая снята;
- наведение: подсвечиваются ВСЕ 8 ячеек строки (`rgb(241,243,246)` =
  `var(--surface-2)`), соседние строки прозрачны;
- шапка: `position: sticky`, при прокрутке контейнера на 300px `top` заголовка
  не изменился (178 → 178);
- ресайз: перетаскивание меняет ширину, ограничения соблюдены (тяга в минус
  дала 60px, тяга на +900 дала 600px);
- localStorage `agl_leads_colw`: после F5 восстановились name=350, comment=600,
  сброшенный phone вернулся к 150;
- двойной клик по зоне захвата возвращает дефолт И убирает ключ из хранилища;
- клик по зоне захвата не меняет сортировку (проверено сравнением
  `leadsState.sort/order` до и после);
- строки одной высоты (все 34px), `overflow:hidden` + `ellipsis` + `nowrap`,
  атрибут `title` на месте;
- колонка «Дело до» ресайзится и сбрасывается наравне с остальными.

Разделы «Клиенты», «Сделки», «Задачи» вообще не используют `<table>` — они
рендерятся карточками, поэтому задеть их нечем; вдобавок все правила скоуплены
под `#leadsTable`.

**Замечание по кэшу.** После правки `index.html` браузер продолжал отдавать
старый `<style>`: у JS есть `?v=`-бастер, у самого index.html — нет. Сервер
отдавал новое сразу (проверено `curl`), но в браузере до жёсткой перезагрузки
CSS не применялся. При UI-приёмке правок в `index.html` — Ctrl+Shift+R
обязателен, иначе легко принять свой же кэш за неработающий код.

## Запись 2026-08-28 — ERP переведён с порта 5555 на 5560

### Что случилось

26.08 в 11:04 сервер перезагрузился. За порт 5555 конкурируют ДВА enabled-юнита:
`agropilot-backend.service` (наш ERP, /opt/agropilot-web) и `agropilot-bff.service`
(`/root/agropilot_bff_new/bff.py` — проект коллеги, отдельный репозиторий).
Кто выиграл гонку при загрузке, тот и слушает порт; второй бесконечно
перезапускается с `address already in use`.

До перезагрузки порт держал наш backend (с 8 августа), а bff падал в цикле —
**153 241** неудачная привязка в `/var/log/agropilot-bff.log` (лог распух до 73 МБ).
После перезагрузки гонку выиграл bff (стартовал на 2 секунды раньше), и уже наш
backend падал **31 541** раз. Всё это время `/agropilot/api/v1/*` отдавал 404:
nginx проксировал на 5555, а bff обслуживает пути `/api/v1/*` — префиксы не
совпадают. ERP был нерабочим ~2 суток, при этом статика отдавалась (сайт 200).

Это уже ТРЕТИЙ случай той же аварии: см. запись от 17.07 — тогда `agropilot.service`
падал 7696 раз с той же ошибкой.

### Решение: ERP уехал на 5560, bff остался на 5555

По решению владельца bff не трогаем — это активная разработка коллеги.
Изменено ровно три строки:

- `/etc/systemd/system/agropilot-backend.service`: `--port 5555` -> `--port 5560`
  (хост остался `127.0.0.1`).
- `/etc/nginx/sites-enabled/agropilot-web`, строки 32 и 190 (блоки :80 и :443):
  `proxy_pass http://127.0.0.1:5555/agropilot/api/;` -> `...:5560/...`.

Бэкапы: `/root/agropilot-backend.service.bak.20260828_141112`,
`/root/nginx-enabled-agropilot-web.bak.20260828_141112`.

**ВНИМАНИЕ на будущее:** `/etc/nginx/sites-enabled/agropilot-web` — НЕ симлинк, а
самостоятельный файл, разошедшийся с `sites-available` (расхождение в секции
`/coach`, чужой проект). Править надо `sites-enabled`, иначе изменения не применятся.

Порядок применения: сначала поднят backend на новом порту, затем `nginx -t` и
`systemctl reload nginx` (не restart). Два warning от `nginx -t` про
`duplicate MIME type` — предсуществующие, в чужой секции.

Проверено после переезда: 8 эндпоинтов = 200 и напрямую на 5560, и через
https://mdked.hlab.kz/agropilot/api/v1/*; сайт 200; данные целы (918 лидов);
bff не потревожен (тот же PID, health 200); соседи через nginx: /coach 200,
/zvec 200, /experience 200, /hub 301.

### Фронт порт не знает

`js/api.js`: `API_BASE = '/agropilot/api'` — относительный путь. Переезд бэкенда
на другой порт фронтенд не затрагивает, пересборки/правок не требуется.

### Не связанное с ERP: docker лежит с 26.08

`docker.service` в состоянии `disabled` и в этой загрузке НЕ стартовал ни разу
(все метки времени systemd пустые, `NRestarts=0`, `/var/run/docker.sock`
отсутствует, процессов `dockerd`/шимов нет). Поэтому n8n, vikunja и стек
flowsint не работают с момента перезагрузки: самая ранняя `connect() failed` на
`127.0.0.1:5678` в логах nginx — 26.08 22:22, задолго до правок этой сессии.
Секция `/n8n/` в конфиге nginx побайтово совпадает с бэкапом — не менялась.
**ИСПРАВЛЕНО 28.08 в 14:3x по просьбе владельца.** `systemctl start docker` —
все 8 контейнеров поднялись сами (у flowsint политика `always`, у n8n и vikunja
`unless-stopped`), данные на диске были целы. Дополнительно выполнено
`systemctl enable docker` + `enable docker.socket`: без этого следующая
перезагрузка снова уронила бы весь стек, а политики рестарта контейнеров прямо
рассчитаны на автозапуск демона. Откат — `systemctl disable docker docker.socket`.

Почему юнит оказался `disabled` — установить не удалось: записей об установке
или обновлении docker в `/var/log/dpkg.log*` нет. Отмечено косвенное:
сборки CLI и демона расходятся (`docker` 29.5.2 build 79eb04c, `dockerd` 29.5.2
build 568f755), что характерно для незавершённого обновления пакета.

Проверено после запуска: n8n отвечает 200 напрямую на `127.0.0.1:5678`, через
nginx `/n8n/` и `/n8n/healthz`; `/hub` 301, `/coach/` 200, `/zvec/` 200,
`/experience/` 200; ERP на 5560 не задет — 8 эндпоинтов 200. n8n работает в
режиме host-сети, поэтому в `docker ps` колонка портов пуста — это нормально,
порт 5678 он слушает напрямую на хосте.

В логе n8n при старте: `Last session crashed` (ожидаемо после жёсткой остановки
демона) и предупреждение, что Python 3 отсутствует для внутреннего task-runner —
предсуществующая особенность конфигурации, работе не мешает.

Память после подъёма стека: занято 4.6 из 7.7 ГБ, доступно 3.1 ГБ.

### Прочее, замеченное попутно

- `agropilot-bff.service` и `agropilot-mock.service` слушают `0.0.0.0`, а не
  `127.0.0.1`. Снаружи закрыты ufw (открыты 80/443/22), но привязку стоит сузить.
- `AGROPILOT_TG_TOKEN` в `/etc/systemd/system/agropilot-tg.service` — маскированная
  заглушка (31 символ, начинается со звёздочек, содержит `***`, формату токена
  Telegram не соответствует). Значение подставляется прямо в URL Telegram API, то
  есть приём из Telegram авторизоваться не может. Это известный сценарий из
  CLAUDE.md (агент записывает залогированное маскированное значение как настоящий
  секрет). `secrets_guard` его не ловит: он следит за файлами в `/root/.openclaw/`,
  а не за systemd-юнитами. Нужен перевыпуск токена бота.
- Реального потребителя у bff не видно: за весь лог (с 15.08) 147 успешных
  ответов, из них 140 — health-check с 127.0.0.1. В `tg_ingest.py` переменные
  `BFF_URL`/`BFF_TOKEN` объявлены, но нигде не используются — приём пишет прямо
  в БД и ходит только в API Telegram.

### Что осталось сделать по этой аварии

Гонка за портом устранена только для нас. Чтобы она не повторилась у коллеги,
стоит договориться о закреплении портов: 5555 — bff, 5560 — ERP, 5557 — tg,
3001 — mock. Зафиксировать в обоих репозиториях.

## Запись 2026-08-28 — §17 A-3 «Мониторинг» реализован

Контракт `0d1320c`, бэкенд `a84b8d7`, фронт `dc36307`. DoD отмечен полностью,
проверка на проде после рестарта (MainPID 321630). Блок A закрыт: разделов без
backend-роутера больше нет.

### Что было

`vMonitoring()` показывал два блока: «Источники» — живые из `/v1/sources`, и
«Сигналы» — ЦЕЛИКОМ из мок-модели `M.signals`. Кнопка «Проверить» отключена
заглушкой «доступно только через BFF». Половина раздела была витриной без данных.

### Что стало

Модуль `backend/monitoring` — read-only лента по существующей таблице
`public.field_alerts` (38 наблюдений: Open-Meteo, Agromonitoring NDVI, NewsAPI,
PriceAPI). `GET /v1/monitoring` с пагинацией и фильтрами level/category/source/
q/since/focus, `GET /v1/monitoring/stats`. Во фронте блок «Сигналы» заменён
живой лентой с фильтром по уровню и пагинацией; флаг `MONITORING_READY`.

### Ключевое: таблица нам не принадлежит

`field_alerts` наполняют внешние процессы (`/root/.openclaw/workspace/mia_monitor.py`),
в репозитории ERP она не упоминалась нигде и миграции на неё нет. Поэтому:
работаем ТОЛЬКО НА ЧТЕНИЕ, схему не меняем, миграцию не заводим. Тот же принцип,
что в §16 E с `deals.stage`.

### Состояние данных — зафиксировано в §17.2, чтобы не принять за наши дефекты

1. **Лента заморожена с 2026-07-11** (47 дней на момент записи). Причина:
   производитель пишет в `agropilot.field_alerts`, а такой таблицы НЕ
   СУЩЕСТВУЕТ — есть только `public.field_alerts`. Его вставки падают. Починка
   вне объёма (чужой репозиторий), но в UI добавлена явная плашка
   «Данные устарели: последнее наблюдение <дата> (N дн. назад)».
2. `level` в двух регистрах — нормализуется ПРИ ЧТЕНИИ. Проверено:
   `level=critical` возвращает 15 = 14 строчных + 1 `CRITICAL`.
3. `category` содержит смысловые дубли (`price`/`prices`, `weather`/`frost`) —
   намеренно НЕ схлопываем, отдаём как есть.
4. `strategy_tasks` ПУСТА, поэтому `monitoring_focus` пуст везде и `matched_focus`
   у всех элементов `[]`, а лента отдаётся полностью. `focus=true` честно
   возвращает 0 — это не ошибка.
5. FK `field_alerts.source` -> `sources.id` НЕТ, `source` — свободный текст.
   Джойн не изобретали.

### Как проверялась пометка по стратегии

Так как `strategy_tasks` пуста, логику §17.4 нельзя было проверить на живых
данных. Заведена временная задача `ST-TEST-17` с `monitoring_focus`
`["заморозок","NDVI"]`: пометки проставились корректно, регистр не помешал
(`заморозок` нашёл `ЗАМОРОЗОК`), `focus=true` отобрал 24 записи, пагинация при
`focus=true` работает. Задача удалена, `strategy_tasks` снова 0 строк,
`field_alerts` не изменена (38 до и после).

Отдельно проверено подозрительное совпадение: системная запись про mock-server
получила метку `NDVI` — в полном тексте её сообщения действительно есть `ndvi`
(перечень непроверенных маршрутов). Подстрочный поиск отработал верно, ложного
срабатывания нет.

### Уточнение в контракте

Строка DoD «latest_at = 2026-07-12» уточнена: API отдаёт `2026-07-11T23:08+00:00`
(UTC), psql показывает то же время в серверной зоне +05 как 12.07. Расхождения
нет, но формулировка могла ввести проверяющего в заблуждение.

### Границы соблюдены (§17.7)

Не тронуты: блок «Источники», «Мой день» зона 3 и `cntSignals()` — продолжают
работать на `M.signals`; кнопка «Проверить» и `signalAction()` остаются
прежними заглушками. Перевод «Моего дня» на живую ленту — отдельный контракт.

### Следующее

- **ПОПРАВКА 28.08 (после аудита):** утверждение выше — «производитель пишет в
  несуществующую `agropilot.field_alerts`» — НЕВЕРНО. Таблица существует, но в
  базе `gbrain` (`gbrain.agropilot.field_alerts`, 58 строк, до 2026-07-21),
  а ERP читает `agropilot.public.field_alerts`. Это разные базы, межбазовых
  запросов в PostgreSQL нет. Полный разбор поставщика и 9 его дефектов —
  в `docs/MONITORING_PRODUCER_AUDIT.md`. Починка отложена по решению владельца;
  там же три варианта целевой архитектуры на выбор.
- Рассинхрон `CLIENTS_READY`/`CONTENT_READY` (флагов в `js/api.js` нет).
- Блок B «Справочник» (tree-view) — последний по плану §7.

## Запись 2026-08-28 — закрыт техдолг CLIENTS_READY / CONTENT_READY

Коммит `7bf8dac`. Вопрос висел с 26.07: HANDOVER заявлял `CLIENTS_READY=true`,
а флага в `js/api.js` не было.

**Разбор снял сам вопрос.** Ни один `*_READY` нигде не читается — 0 упоминаний
в `app.objects.js`, `index.html`, `mock.objects.js` и в самом `api.js` вне блока
объявлений. Это ДОСКА СТАТУСОВ («backend по разделу поднят»), а не переключатели
поведения. Значит рассинхрон никогда не был функциональным багом и ничего не
ломал — он вводил в заблуждение читателя документации.

Решение: доску привели в соответствие с кодом (добавлены `CLIENTS_READY` и
`CONTENT_READY` — оба роутера зарегистрированы, оба эндпоинта отдают 200), а над
блоком написали, чем он является. Без этой приписки следующий разработчик снова
будет искать несуществующие переключатели.

Попутно исправлен устаревший комментарий в `backend/main.py`: он обещал
`clients_router` как будущий, хотя роутер подключён строкой выше. Заменён на
актуальный ориентир — `catalog_router` (Блок B).

### Состояние доски статусов на 2026-08-28

`CALENDAR_READY`, `SKILLS_READY`, `STRATEGY_READY`, `DEALS_READY`, `TASKS_READY`,
`STRATEGY_TASKS_READY`, `STRATEGY_VIEW_READY`, `SOURCES_READY`, `LEADS_READY`,
`TEAM_RBAC_READY`, `MONITORING_READY`, `CLIENTS_READY`, `CONTENT_READY` — true.
`VERSIONS_READY` — false (единственный false, роутер `deals_versions` подключён,
но раздел не принят).
Нет флага только у Блока B «Справочник» — он не начат.
