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
