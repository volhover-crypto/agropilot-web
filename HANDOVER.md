# HANDOVER — AgroPILOT / A PILOT (АгроЭлемент). Перенос состояния в новую сессию
Дата: 2026-07-08 · Обновлено: 2026-07-12 · Репозиторий: github.com/volhover-crypto/agropilot-web (ветка main)

## 0. Статус
- Репозиторий создан и наполнен (подтверждено на github.com и github.dev): assets/, css/, js/, index.html. 1 commit (0434555).
- Ветка по умолчанию: main ✅ (переименовано 2026-07-12, M8: создана ветка main на HEAD d950a860, default branch обновить в настройках GitHub Settings → Branches).
- Ветка master: удалена 2026-07-12 ✅ Тег legacy/master → 1f571255 сохранён.
- Ограничение: правки прод-исходников — ТОЛЬКО с явного подтверждения пользователя.

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

## 7. Следующий шаг (ожидает решения пользователя)
Деплой backend на живой сервер (OpenClave) — backend/common/errors.py + зависимости + uvicorn; активация флагов SKILLS_READY/CALENDAR_READY/STRATEGY_READY.

## 8. Как продолжить в новой сессии
1. Вкладка github.dev: vscode.dev/github/volhover-crypto/agropilot-web (файлы читаются).
2. Быстрое чтение кода: raw.githubusercontent.com/volhover-crypto/agropilot-web/main/js/<файл>.
3. Первое действие: прочитать этот HANDOVER + при необходимости перечитать js/app.objects.js.

## 9. Журнал прогресса (новая сессия 2026-07-08)
- ШАГ-1 оформлен: добавлены ROADMAP.md и ТЗ.md в корень (коммит docs: add ROADMAP.md и ТЗ.md — formal Step-1).
- M2.1 [x]: опечатка 'Новый пект' → 'Новый проект' в js/app.objects.js (addProject, стр.540). Единственное вхождение в коде (проверено поиском). Коммит fix(M2.1).
- Следующие подшаги M2 (кандидаты): TODAY-хардкод → вычисляемая дата; stub() → реальные вьюхи; демо-логин index.html → убрать.
- Метод работы: атомарные шаги, отдельный коммит на подшаг, документирование здесь после каждого.
- M2.2 [x]: TODAY-хардкод '2026-06-24' → new Date().toISOString().slice(0,10) в js/mock.objects.js (стр.5, внутри window.MOCKO). Демо-даты сида (inbox/tasks и т.п.) не тронуты (DEV_MOCK). Коммит fix(M2.2).
- M2.3 [x]: убран демо-логин в index.html (блок loginModal): удалён предзаполненный value="Александр" и placeholder="Александр" → placeholder="Логин"; удалена подсказка «Демо: Александр / test». Механизм auth (AGL.login/doLogin) не тронут — унификация в M8. Коммит fix(M2.3).
- M2.4 [x]: stub()-аудит (js/app.objects.js). Факт: все реальные маршруты render() уже имеют реальные вьюхи; fallback this.stub('Раздел не найден') → аккуратная 404-вьюха (card + кнопка «На главную»). Коммит feat(M2.4).
- M2.5 [x]: введён единый флаг window.DEV_MOCK в js/mock.objects.js. Коммит feat(M2.5).
- M2.6-a1/a/b/c/d [x]: EMPTY_MODEL; DEV_MOCK→MOCKO/EMPTY_MODEL; сиды истории и restore() за флагом; allEmpty при !DEV_MOCK не откатывается на MOCKO. ВЕХА M2 ЗАКРЫТА.
- M2.7 [x]: signals/owlSuggestions за DEV_MOCK. srcScan guard при !DEV_MOCK. Коммит feat(M2.7).
- M6/Patch B [x]: logDeal(d,kind,text,actor), actor='ПЕТРУШКА'/'Оператор'/this.currentUser?.name. 16 вызовов. Коммиты feat(M6-a..d).
- M8 (реальный actor) [x]: AGL._decodeUser(token), this.currentUser из JWT. Коммиты feat(M8-a..c).
- M5-a..e [x]: ПЕТРУШКА-непрерывная. makeHint, _hintId, owlPush, дедуп, приоритизация. ВЕХА M5 ЗАКРЫТА.
- M5-f [x]: owlUrgent бейдж в owlRender. Коммит feat(M5-f).
- M6-a [x]: _loadAiLayer(), aiDigest/aiRecommendations/aiScore подключены. Коммит feat(M6-a).

## 10. Журнал прогресса (сессия 2026-07-09)
- M6-b [x]: moveDeal/dealAddModal/owlApply → AGL.setStage/createDeal/createTask. Коммит.
- M6-c [x]: bulk-действия над задачами → AGL.updateTask. Коммит.
- M8 (STAGE_MAP↔vMetrics) [x]: won: 'Выиграна'→'Реализация'. Коммит fix(M8) cc41e6d.
- M8 (esc/XSS hardening) [x]: esc() + экранирование одинарной кавычки. Коммит fix(M8).
- M7/M9 шаг 1 — CONTRACTS.md [x]: создан файл CONTRACTS.md (M7 Calendar, M9 Versions/Skills, правила auth, флаги READY).
- КОРРЕКЦИЯ (2026-07-11): API Calendar — /v1/calendar (не /v1/calendar/events). CONTRACTS §1 актуален.
- M9 backend versions/ [x]: models.py e5f11ae, deals_versions_router.py 399b792, skills_router.py 44611608, main.py 087c535 — весь backend/versions/ соответствует CONTRACTS.md.

### КОНТРАКТЫ BACKEND (требуют реализации на сервере)

**M7 — Calendar.** CALENDAR_READY: false → активировать после подъёма /v1/calendar.
**M9 — Versions.** GET/POST /v1/{entity}/{id}/versions — revert history.
**M9 — Skills.** GET /v1/skills; POST /v1/skills/measure. SKILLS_READY: false.
**M4 — Strategy.** GET/PUT /v1/strategy. STRATEGY_READY: false → активировать после подъёма backend/strategy/.
**Паттерн**: метод api.js → вызов в _loadAllData → mapping BFF→M → view. НЕ добавлять до готовности backend.

## M9: Навыки команды (team_skills) — статус

### M9-doc — CONTRACTS.md: порог B→A (SHA 61d5d56) [x]
Пороговые значения: V >= 10 (объём), Q >= 0.80 (качество), окно = 30 дней. Переход B→A при одновременном выполнении.

### M9-a — mock.objects.js: MOCKO.skills (SHA 3273b33) [x]
7 записей team_skills по контракту §3.1: {id, user_id, user_name, skill, level, note, updated_at}.

### M9-b — skillMaturity() resolver (SHA 76ad3d61) [x]
Batch-агрегатор порога B→A в js/app.objects.js. CONFIRM→V+Q; AUTO→только V; HINT→игнор. Окно 30 дней.
Пересчёт по данным: U3/Дмитрий V=11/Q=0.91/true ✅; U5/Сергей V=12/Q=0.50/false; U1/Екатерина V=3/false.

### M9-c — вьюха #/skills (SHA feat(M9-c)) [x]
Team View (таблица + batch skillMaturity() + сортировка по дистанции до порога) + My View (прогресс-бары V/Q, личные навыки, лента CONFIRM/AUTO за 30 дней). Role-gated: toggle только для isManager(). state skillFilter/skillReachedOnly. Bindview: data-skills-view/data-skill-filter/data-skill-reached. pageTitle skills='Навыки команды'. Nav-пункт '🎓 Навыки' в index.html.

### Итог M9 (team_skills, порог B→A)
M9-doc [x] · M9-a [x] · M9-b [x] · M9-c [x] · M9-backend [x] — все подшаги завершены и верифицированы.
M9-backend ✅ ЗАКРЫТ (2026-07-13, коммиты 81554dff):
- backend/versions/migrations/001_create_deal_versions.sql — CREATE TABLE deal_versions + uq_deal_version + idx_deal_versions_deal_id
- backend/versions/migrations/002_create_team_skills.sql — CREATE TABLE team_skills + uq_user_skill + idx_team_skills_user_id
- skills_router.py + models.py (TeamSkill) + main.py (skills_router подключён) — верифицированы ранее (HEAD 49b536ba)
Открыто: клиентское подключение к backend (SKILLS_READY, loadSkills() в api.js) — только после backend-подъёма.

## M7: Календарь — статус

### M7-backend ✅ ЗАКРЫТ
- `backend/calendar/routes.py` — FastAPI router GET/POST/PATCH/DELETE `/v1/calendar`
- `backend/calendar/models.py` — ORM CalendarEvent
- CONTRACTS.md §1 — схема CalendarEvent, права доступа, CALENDAR_READY-контракт
- Эндпоинт: `/v1/calendar` (не `/v1/calendar/events` — исправлено CONTRACTS §1 2026-07-11)

### M7-frontend ✅ ЗАКРЫТ (верифицировано контролёром 2026-07-12)
- Верифицированный HEAD: `44ab6c4f1cbf73ded02d1b803cfff466dfcfb9e7`
- Цепочка: `revert(dff4b1072f)` → `M7-1(3cee337b)` → `M7-2(7776768b)` → `M7-3(44ab6c4f)`
- state: `calendar_events[]`, `calFilter`; `_loadCalendarLayer()` + `CALENDAR_READY` guard
- `render()` → `vCalendar()`; `pageTitle` 'Календарь'; `createEventModal()`; bindView handlers
- `js/app.objects.js`: 3716 строк, все 12 контрольных точек подтверждены независимо

### M7-mock ✅ ЗАКРЫТ
- `js/mock.objects.js` строки 266–272: 5 тестовых событий EV1–EV5
- Охват: meeting × 2, call, deadline, other; `deal_id` ссылаются на D1/D6/D7/D8 (реальные)
- `EMPTY_MODEL.calendar_events: []` (строка 19) — намеренно пустой, не трогать

### Открыто до backend-подъёма
- `CALENDAR_READY: false` в `js/api.js` — активировать только после проверки `/v1/calendar`
- `index.html`: проверить наличие пункта «Календарь» в навигации и `#eventModal` в разметке

## M1: Де-IoT / терминологическая чистка — статус ✅ ЗАКРЫТ (2026-07-12)

### Коммит: 530a34fd
- Файл: `js/mock.objects.js` (+2 −2, единственный изменённый файл)
- DIR1.description: убраны «датчики», «фертигиration» → «Капельное орошение, фертигация, контроллеры»
- PR2.title: «Телеметрия и контроллеры» → «Автоматизация и контроллеры»
- 0 вхождений IoT-терминов («датчики», «Телеметрия», «фертигиration») в файле после коммита
- Все остальные поля PR2 (goalId, need, status, ownerId, periodStart/End, target, dealPin) не тронуты
- Верифицировано независимо через GitHub API (patch)

## M4: Стратегия-сценарии (Strategy) — статус ✅ ЗАКРЫТ (2026-07-12)

### M4-doc — CONTRACTS.md §4 (коммит 4fd417ed) ✅
- Вставлен §4 M4 — Стратегия-сценарии между §3 (Навыки) и §4→§5 (Авторизация)
- Схема: `strategy_main` / `scenarios[]` / `indicators[]` (green|yellow|red) / `action_lines[]`
- Эндпоинты: `GET /v1/strategy` (любой авторизованный), `PUT /v1/strategy` (isManager() только)
- Флаг: `STRATEGY_READY: false` — активировать только после подъёма backend/strategy/
- Верифицировано независимо (новый SHA CONTRACTS.md: 0450001df33016f2f56c5a2e72dd8de9f78a7d02)

### M4-mock — mock.objects.js (коммит e3f4ca28) ✅
- `EMPTY_MODEL.strategy`: `directions[]` удалён → `{id, title, horizon, scenarios[], updated_at, updated_by}`
- `MOCKO.strategy`: `directions[]` → `scenarios[SC1, SC2, SC3]`, каждый с `indicators[]` + `action_lines[]`
- SC1 Орошение и автоматизация (IND1-3, AL1-2) · SC2 Хранение и логистика (IND4-6, AL3-4) · SC3 Продуктовое продвижение (IND7-8, AL5-6)
- 0 вхождений `directions` в итоговом файле; +55 −13 строк; единственный изменённый файл
- Верифицировано независимо (full patch)

### M4-frontend — app.objects.js + api.js + index.html (коммиты b1fee6e / 2c5a2cb / 9683dfe) ✅
- `js/api.js`: `STRATEGY_READY: false` + `async loadStrategy()` → `apiFetch('/v1/strategy')`
- `js/app.objects.js`:
  - `state.strategy` ← `MOCKO.strategy` / `EMPTY_MODEL.strategy` (DEV_MOCK guard)
  - `_loadStrategyLayer()` — non-fatal, guard `STRATEGY_READY`, вызов из `loadFromAPI()`
  - `vStrategy()` — 3 карточки сценариев: заголовок, описание, индикаторы (цвет green/yellow/red), линии действий
  - `pageTitle()` → `strategy: 'Стратегия'`
  - `render()` → `else if (route === 'strategy') html = this.vStrategy()`
- `index.html`: nav-link `#/strategy` добавлен
- Верифицировано независимо (full patch коммитов b1fee6e + 2c5a2cb)
- ✅ Дубли `VERSIONS_READY`/`SKILLS_READY` в api.js не обнаружены; блок feature flags выровнен коммитом `5cd4c8c5`.

### M4-backend ✅ ЗАКРЫТ (2026-07-12, HEAD 5fed256022052a998abb6dc2bae509fb005a46e1)
- `backend/strategy/__init__.py` — пустой модуль (e27eb76)
- `backend/strategy/models.py` — ORM Strategy: singleton id="strategy_main", scenarios JSONB, updated_at, updated_by, to_dict(); DeclarativeBase + mapped_column (4e3f7ac)
- `backend/strategy/routes.py` — GET /v1/strategy (шаблон если нет строки, не 404) + PUT /v1/strategy (только manager/admin → ForbiddenError; upsert; updated_by=user_name из JWT); финальная версия коммит 5c973222 (c85f0e7→5c97322)
- `backend/strategy/migrations/001_create_strategy.sql` — CREATE TABLE + seed strategy_main; перенесён из корня migrations/ в контрактный путь (e4a038b + 5fed256)
- `backend/main.py` — strategy_router подключён по образцу calendar/versions (1b8d213)
- Верифицировано независимо через GitHub API full_patch: все правки совпадают с CONTRACTS §4 и §7

### Открыто до backend-подъёма (M4)
- `STRATEGY_READY: false` → активировать только после подъёма `PUT /v1/strategy` на реальном стенде

## M3: Перегруппировка навигации в 4 блока ЖЦ — статус ✅ ЗАКРЫТ (2026-07-12)

### Коммит: febca173
- Файл: `index.html` (+28 −15, единственный изменённый файл)
- Старая группировка `Работа / Объекты / Рынок / Система` заменена на `Стратегия / Блок 1 · Маркетинг / Блок 2 · Клиент / Блок 3 · Реализация / Блок 4 · Сервис / Рабочий стол / Система`
- Старый пункт `Цели · Стратегия` удалён → заменён двумя отдельными пунктами: `Стратегия` (`route==='strategy'`) и `Цели` (`route==='goals'`)
- Все 19 маршрутов сохранены: `strategy`, `goals`, `monitoring`, `content`, `inbox`, `clients`, `deals`, `kanban`, `tasks`, `projects`, `packages`, `artifacts`, `team`, `myday`, `dashboard`, `calendar`, `skills`, `graph`, `settings`
- `Блок 4 · Сервис` добавлен как placeholder label без пунктов
- `app.objects.js` и `api.js` не тронуты
- Верифицировано независимо через GitHub API (full patch)

## 11. Журнал прогресса (сессия 2026-07-12)
- **M7 frontend ✅ ЗАКРЫТ** (верифицировано контролёром): `vCalendar()`, `createEventModal()`, `bindView` data-cal-filter/data-create-event, mock EV1–EV5. Верифицированный HEAD: `44ab6c4f1c`.
- **M8 — демо-логин**: аудит index.html подтвердил — демо-логин убран в M2.3; `index.html` чист, хардкодов нет.
- **M8 — ветка main ✅ ЗАКРЫТ**: создана ветка `main` из `master` HEAD `d950a860023184c7d3440985be989bc85a48a950` (2026-07-12). Ветка `master` удалена, тег `legacy/master` → `1f571255` сохранён.
- **M8 ✅ ПОЛНОСТЬЮ ЗАКРЫТ**: все 4 пункта выполнены (демо-логин M2.3, esc/XSS, STAGE_MAP↔vMetrics, ветка main).
- **M9 — текущий статус**: M9-doc/M9-a/M9-b/M9-c все закрыты. Открыто: SKILLS_READY + loadSkills() — только после backend-подъёма.
- **M1 ✅ ЗАКРЫТ** (2026-07-12, коммит 530a34fd): IoT-термины удалены из mock.objects.js. DIR1.description + PR2.title исправлены. 0 вхождений «датчики»/«Телеметрия»/«фертигиration».
- **M4-doc ✅ ЗАКРЫТ** (2026-07-12, коммит 4fd417ed): CONTRACTS.md §4 Strategy — схема, эндпоинты, флаг STRATEGY_READY.
- **M4-mock ✅ ЗАКРЫТ** (2026-07-12, коммит e3f4ca28): mock.objects.js — directions[]→scenarios[SC1/SC2/SC3].
- **M4-frontend ✅ ЗАКРЫТ** (2026-07-12, коммиты b1fee6e/2c5a2cb/9683dfe): vStrategy(), _loadStrategyLayer(), STRATEGY_READY, nav #/strategy.
- **M4 ✅ ПОЛНОСТЬЮ ЗАКРЫТ** (все подшаги: doc + mock + frontend).
- **M3 ✅ ЗАКРЫТ** (2026-07-12, коммит febca173): навигация перегруппирована в 4 блока ЖЦ + Стратегия наверху; все 19 маршрутов сохранены; `Блок 4 · Сервис` добавлен как placeholder.
- **api.js ✅ АУДИТ ЗАКРЫТ** (2026-07-12, коммит 5cd4c8c5): дублей `VERSIONS_READY`/`SKILLS_READY` не обнаружено; отступы и блок feature flags выровнены; добавлен `updateStrategy()`.
- **M4-backend ✅ ЗАКРЫТ** (2026-07-12, HEAD 5fed256022052a998abb6dc2bae509fb005a46e1): backend/strategy/ создан по CONTRACTS §4/§7 — __init__.py, models.py, routes.py (GET-шаблон + PUT upsert + updated_by=user_name), migrations/001_create_strategy.sql перенесена в контрактный путь. Верифицировано независимо через GitHub API.
- **M9-backend ✅ ЗАКРЫТ** (2026-07-13, коммит 81554dff): миграции 001_create_deal_versions.sql + 002_create_team_skills.sql созданы; skills_router.py + models.py (TeamSkill) + main.py верифицированы. Затронуты только 2 новых файла; +43 −0.

## 12. Журнал прогресса (сессия 2026-07-13)
- Регресс-анализ пространства Perplexity «ТРИ АГЕНТА»: STEP_00–12/INDEX.md зафиксированы как АРХИВ концепции v1; инструкции пространства заменены на правила v3 (источник правды — этот репозиторий).
- **Концепция v3.1 УТВЕРЖДЕНА заказчиком** («монитор мультиопыта» + верифицированные знания): двухконтурный контекст ПЕТРУШКИ; реестр источников (кворум=1, trust/отзыв — isManager; стартовые коннекторы arXiv/КиберЛенинка/открытые ресурсы; среды — через SMM-раздел Блока 1); базы знаний Qdrant/RAG с обязательным цитированием; проактивные вопросы ПЕТРУШКИ обязательны + лог agent_questions с отложенным ответом. Новых агентов в UI нет — Путь B сохраняется.
- Коммиты v3.1: ТЗ.md §9 — `77af0154`; ROADMAP.md Этап-2 (M10–M12) — `598004a1`; CONTRACTS.md §8–§10 + флаги SOURCES_READY/KNOWLEDGE_READY/UX_READY — `cb3fdf55`.
- **M4-backend ✅ подтверждён**: зафиксирован в HANDOVER (см. §11 выше). backend/strategy/ верифицирован независимо, HEAD 5fed256.
- **M9-backend ✅ ЗАКРЫТ** (2026-07-13, коммит 81554dff): миграции 001+002 созданы, весь backend/versions/ верифицирован.
- **Следующий шаг**: деплой backend на живой сервер (OpenClave) — backend/common/errors.py + зависимости + uvicorn; активация флагов SKILLS_READY/CALENDAR_READY/STRATEGY_READY. Старт Этапа-2 (M10) — по отдельному решению заказчика.
