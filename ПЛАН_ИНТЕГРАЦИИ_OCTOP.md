# План интеграции механик Octop (О1–О7)
Рабочий план · Реализация ТЗ_ИНТЕГРАЦИЯ_OCTOP.md от 27.09.2026 · сопоставление с
фактическим состоянием репо на 27.09.2026 (HEAD 5d4ccee) · Этап-2

## 0. Назначение
Документ фиксирует: (а) фактическое состояние каждой механики, на которую
опирается ТЗ; (б) расхождения ТЗ ↔ код и их разрешение; (в) минимальные шаги
реализации по блокам в порядке исполнения ТЗ §5; (г) решения, требующие
утверждения заказчиком до правок.

Правило ТЗ §5 сохраняется: каждый блок — анализ → согласование → правки в
исходники (только после подтверждения заказчика) → верификация по DoD →
фиксация (commit + CONTRACTS.md).

---

## 1. Сводка соответствия «ТЗ → текущая механика»

| Блок | Что требует ТЗ | Фактически в репо | Дельта | Объём факт |
|---|---|---|---|---|
| О7 Гигиена | AGENTS.md, CodeQL, argon2, PKCE | Нет AGENTS.md, нет CI (`.github/` отсутствует), bcrypt 4.3.0 напрямую (`backend/auth/security.py`), esc() покрывает ~19% интерполяций | Всё новое | S |
| О4 Таймзоны | DEFAULT_TZ в конфиге BFF, явный TZ у всех расписаний | Код — везде UTC; расписания снаружи BFF: systemd-таймеры (`deploy/systemd/`, Europe/Moscow) + n8n (GENERIC_TIMEZONE=Europe/Moscow). Планировщика в BFF нет | Конфиг-модуль + фиксация слоя TZ | S |
| О2 Коннекторы (M10) | Слой коннекторов, реестр, verified-only, PKCE | `backend/sources/` (CRUD), сборщики в `backend/news/collectors.py` (rss/telegram-web/site, stdlib), `backend/connectors/` нет. Статусы **proposed/active/disabled/rejected** (не verified/revoked) | Новый каталог + реестр + миграция синхронизации типов | M |
| О1 RAG (M11) | Конвейер документа, Qdrant, цитирование, corpus_version | Ничего нет: §9 описывает `knowledge_bases`+corpus_version, код/миграции отсутствуют. Qdrant/эмбеддинги/чанки — 0 упоминаний. `/v1/orchestrator/chat` в бэкенде отсутствует (фронт зовёт `js/api.js:477`, работает fallback) | Контур с нуля + зависимости | L |
| О3 Вопросы (M12) | TTL 72ч, идемпотентность показа, гашение раунда | Таблицы/кода/фронта `agent_questions` нет вообще (только контракт §10). Аналог TTL-механики: SLA 2ч в content (§35) | Миграция + роутер + фронт — не «S», а **M** | M |
| О5 RFC | Документ mailbox/delegation | Аудит-база есть: `run_logs` (мигр. 032), `agent_cards` (028). Q-метрики M9 **нигде не определены** (одно упоминание §10.2) | Документ; начать с формализации Q-метрик | S |
| О6 Telegram | channel_bindings, webhook, notify_mask | TG уже в 3 контурах на **polling** (getUpdates): `backend/inbound/tg_poller.py` (JARVIS_MONITOR), digest (`myday/routes.py`), публикация (`content/routes.py`). `channel_bindings` нет; `backend/channels` — это каналы публикаций §21, не трогаем | Новый контур; отдельный бот | M |

---

## 2. Расхождения ТЗ ↔ проект и их разрешение

**Р1 · Нумерация секций CONTRACTS.md.** ТЗ §4 предлагает новые секции §20–§23 —
они **заняты** (§20 news_items, §21 каналы публикаций, §22 входящие, §23 роли;
фактический максимум — §38, порядок в файле не монотонный). Разрешение: новые
секции получают следующие свободные номера — О1→§39, О2→§40, О3→§41, О6→§42
(перед написанием проверить максимум grep'ом `^## §`).

**Р2 · Статусная модель sources.** ТЗ О2 опирается на статусы §8.1
(verified/revoked), но §8 перекрыт ревизиями §13.1 и §20.1: в коде и БД —
`proposed/active/disabled/rejected` (`backend/sources/routes.py:23`).
Разрешение: **не менять** фактическую статусную модель; правило ТЗ
«verified-only» трактуется как «данные поставляют только источники с
`status='active' AND active=true`» (маппинг зафиксировать в новой секции §40).
Проверка `Source.active.is_(True), Source.status == "active"` уже существует в
`backend/news/routes.py::scan_sources` — поднять её в единый фильтр
коннекторного слоя.

**Р3 · Конфликт типов sources (код ↔ БД).** Код: `news/supplier/competitor/
market/tech` (`routes.py:22`); миграция 017 навязала БД-CHECK
`news/telegram/site/rss`. Создание supplier-источника через API упадёт на
INSERT. Разрешение: миграция синхронизации в О2 (решение D2 — какой набор
канонический; рекомендация: принять `news/telegram/site/rss` из 017 как
канонический, «смысловые» роли источника хранить в `scope`).

**Р4 · Легаси-имена механик.** `orchChat` и `aiDigest` в бэкенде отсутствуют:
текущий ассистент — `POST /v1/assistant/ask` (`backend/assistant/routes.py`,
stateless, контекст из БД, LLM через OpenRouter `backend/common/llm.py`,
логирование `run_logs`); текущий дайджест — `POST /v1/myday/digest`
(внешний запуск `backend/myday/send_digest.py`). Разрешение: в новых секциях
контрактов использовать фактические иена эндпоинтов; «aiDigest» = myday-digest
цикл, «orchChat» = целевой knowledge-aware эндпоинт (решение D3).

**Р5 · Планировщик джоб.** APScheduler в BFF нет; все расписания — systemd
(по образцу `deploy/systemd/agropilot-meteo@*.timer`) и n8n. Разрешение:
expire-джоба О3 — systemd-таймер `agropilot-questions-expire.timer` + ленивая
проверка TTL при чтении (GET помечает просроченные); никакой новый планировщик
в BFF не вводится. О4 ограничивается конфигом DEFAULT_TZ и фиксацией единого
TZ-слоя (systemd и n8n уже на Europe/Moscow).

**Р6 · Telegram webhook vs polling.** ТЗ О6 требует webhook c secret-token;
на том же токене бота JARVIS_MONITOR работает getUpdates-polling — совмещать
нельзя. Разрешение: для канала ПЕТРУШКИ — **отдельный бот** (новый токен,
webhook); JARVIS_MONITOR не трогаем (решение D7).

**Р7 · Оценки объёма.** О3 в ТЗ — S («таблица уже содержит статусы»), но
реализации нет даже таблицы: фактически миграция + роутер + фронт = M
(ROADMAP_M10 сам помечает agent_questions как «отдельная миграция + роутер»).
О1 расширяет requirements.txt с 7 пакетов до ~12+ (см. блок О1) — это
существенное отклонение от текущей «stdlib-минимализм» дисциплины.

---

## 3. План по блокам (в порядке исполнения ТЗ §5)

### Этап 0 — сразу, вне очереди вех

#### О7 · Инженерная гигиена (S)
Текущее: см. таблицу §1.
Шаги:
1. **AGENTS.md в корне** (аналог хендбука Octop): карта модулей `backend/*`;
   жёсткие запреты — не править `js/mock.objects.js` при `DEV_MOCK=false`
   (прод-режим, `index.html:252`); `esc()` (`app.objects.js:419`) обязателен
   для всех пользовательских данных в template-literal интерполяциях и
   `innerHTML` (сейчас ~19% покрытия — рост по мере правок, не большой банг);
   прод-деплой (`git pull` на `/opt/agropilot-web`, `root@mdked.hlab.kz`) —
   только после явного подтверждения заказчика; связка с COMET_PROMPT.md,
   OPENCLAW_PROMPT.md, HANDOVER.md, CODER_BRIEF.md.
2. **CodeQL**: `.github/workflows/codeql.yml` (python + javascript, адаптация
   codeql.yml Octop, MIT-лицензия совместима). Remote уже есть
   (`github.com/volhover-crypto/agropilot-web`).
3. **argon2-cffi** (после утверждения D6): `backend/auth/security.py` —
   `verify_password`: попытка argon2 → fallback bcrypt → при успехе перехэш
   argon2id в `hash_password`; `argon2-cffi` в requirements.txt. auth-зона —
   правка только после явного подтверждения.
4. PKCE — реализуется внутри О2 (п.4).
Верификация DoD: AGENTS.md закоммичен; вкладка Actions — CodeQL зелёный;
вход пользователя со старым bcrypt-хешем проходит, в `team.login` хеш
становится argon2 (проверка на тестовой БД).

#### О4 · Таймзоны (S)
Текущее: БД и код — timestamptz/UTC везде; systemd-таймеры и n8n —
Europe/Moscow; «голые» времени в API не протоколированы.
Шаги:
1. `backend/common/tz.py` (или расширить существующий common-конфиг):
   `DEFAULT_TZ = ZoneInfo(os.getenv("DEFAULT_TZ", "Europe/Moscow"))`,
   `now_local()`, `parse_dt()` — ISO без offset трактуется как DEFAULT_TZ.
2. `DEFAULT_TZ=Europe/Moscow` в `.env.example` (+ вычистка: добавить в example
   реально используемые ключи — OPENROUTER_API_KEY, TELEGRAM_* и пр., отдельным
   маленьким коммитом).
3. Фиксация TZ-слоя в AGENTS.md: systemd=Europe/Moscow, n8n=Europe/Moscow,
   БД=UTC, API=ISO 8601 с offset; все новые джобы — только с явным TZ.
4. Сверка хоста: на сервере проверить `timedatectl` на расхождение МСК/UTC и
   совпадение OnCalendar-зон таймеров (одна ручная проверка, протокол в AGENTS.md).
Верификация DoD: локальный тест — смена TZ хоста не влияет на расчёт
расписаний (юнит-тест `parse_dt` + проверка, что systemd-юниты не зависят от
зоны хоста).

### Веха M10

#### О2 · Коннекторный слой (M)
Текущее: сборщики `backend/news/collectors.py` (rss/telegram-web/site,
stdlib), scan-фильтр active в `news/routes.py`; коннекторов arXiv/КиберЛенинки
нет; httpx/feedparser отсутствуют.
Шаги:
1. **Миграция 036** (следующий номер по фактическому максимуму — проверить):
   синхронизация CHECK `sources.type` с кодом (Р3/D2); колонка
   `connector varchar(48)` (ключ реестра, nullable).
2. `backend/connectors/`: `base.py` (интерфейс коннектора: `key`, `kind`,
   `auth: none|apikey|oauth`, `fetch(params) -> [observation]`,
   `normalize() -> insights/ux_signals`-структура), `registry.py` (реестр:
   словарь ключ→модуль), `rss.py` (перенос и обёртка `collect_rss`),
   `arxiv.py` (API arXiv, auth:none, OpenAlex-коннектор Octop — референс),
   `cyberleninka.py` (web/search, auth:none). HTTP — stdlib `urllib.request`
   по текущей дисциплине проекта (новые пакеты не вводим; httpx — только если
   заказчик утвердит).
3. Единая точка verified-only (Р2): фильтр `status='active' AND active=true`
   в реестре/диспетчере — наблюдения всегда несут `source_id`; proposed/
   disabled/rejected источники не поставляют данные (перенести проверку из
   `scan_sources` в слой коннекторов).
4. OAuth+PKCE (для будущих apikey/oauth-источников): `connectors/oauth.py` —
   код-обмен PKCE S256, whitelist redirect-uri; в M10 не активируется (нет
   oauth-источников в стартовом наборе), код и контракт готовы.
5. CONTRACTS §40: интерфейс коннектора, реестр, правило active-only (Р2),
   PKCE.
Верификация DoD: 1) `python -m backend.connectors.arxiv --test` (или pytest)
возвращает нормализованные наблюдения с source_id; 2) источник в статусе
proposed не отдаёт данные в scan (pytest на фильтре); 3) добавление нового
rss-источника — строка в `sources` без правок кода (ручная проверка через
POST /v1/sources + scan).

### Веха M11

#### О1 · RAG-контур (L) — перед стартом: инфра-согласование (D4, D5)
Текущее: знаний нет вообще; §9.1 описывает `knowledge_bases` (corpus_version
уже в контракте); LLM-шлюз и `run_logs` существуют (`backend/agents/runlog.py`,
`backend/common/llm.py`).
Предпосылки (решения заказчика до старта):
- D4 эмбеддинги: «провайдер, уже подключённый к BFF», не существует — выбрать
  (а) fastembed локально (без ключей; рекомендую, несмотря на позицию ТЗ «вне
  MVP» — это минимальный путь без нового секрета) или (б) внешний
  embeddings-API с отдельным ключом.
- D5 инфраструктура: Qdrant (docker) и rapidocr на сервере BFF.
Шаги:
1. **Миграция**: `knowledge_bases` (по §9.1, включая corpus_version),
   `knowledge_docs` {id, kb_id, title, status: uploaded→parsed→chunked→
   indexed→ready|failed, fail_reason, charset, size, created_at},
   `knowledge_chunks` {id, doc_id, kb_id, ord, quote_start, quote_end,
   qdrant_point_id}.
2. `backend/knowledge/`: `models.py`, `routes.py` (загрузка/листинг/повтор
   конвейера по doc_id), `ingest.py` (идемпотентный конвейер: очистка точек
   Qdrant по doc_id перед переиндексацией; кодировки UTF-8→cp1251→
   `failed(encoding)`; OCR-отказ → `failed(no_text)`, НЕ ready с пустым
   корпусом), `chunking.py` (CHUNK_SIZE=1000, CHUNK_OVERLAP=15% — конфиг
   BFF), `embed.py` (EMBED_PROVIDER), `citations.py`.
3. **orchChat** (D3): новый роут `POST /v1/orchestrator/chat` — knowledge-aware
   путь над существующим assistant: ретрив по KB → контекст из чанков с
   цитатами; при валидных citations[] = {doc_id, title, chunk_id, quote} —
   ответ с бейджем «знание»; пустой ретрив или невалидные citations →
   `unverified`-деградация в обычный чат (без значка). `/v1/assistant/ask`
   не меняется. corpus_version фиксировать в `run_logs` (meta/payload записи
   LLM-вызова).
4. Фронт: рендер `m.citations` в диалоге ПЕТРУШКИ (`app.objects.js` ~1272–1303,
   ветка `petSend` ~920 уже зовёт `AGL.orchChat`) — значок «знание», клик
   doc → chunk → подсветка quote (модал по образцу существующих ui-reka).
5. Зависимости (после утверждения): `qdrant-client`, `pypdf`,
   `python-docx`, `openpyxl`, `rapidocr-onnxruntime` (+fastembed при D4-а).
6. CONTRACTS §39: статусы конвейера, схема citations, corpus_version,
   EMBED_PROVIDER, правило unverified.
Верификация DoD: тестовый корпус из 5 файлов (pdf с текстом, pdf-скан,
docx cp1251, csv, битый) → все 5 исходов конвейера воспроизводятся (pytest +
ручная загрузка); knowledge-запрос без ретрива не даёт значок; повторная
индексация doc_id не создаёт дублей в Qdrant (count точек до/после);
corpus_version виден в run_logs. Прогон полноты ответов на реальном корпусе
до прода (риск ТЗ §6).

### Веха M12

#### О3 · Вопросы агента (M — не S, см. Р7)
Текущее: реализация отсутствует полностью (таблицы, роутера, фронта нет).
Шаги:
1. **Миграция**: `agent_questions` по §10.1 + `expires_at` (created_at +
   AGENT_QUESTION_TTL, default 72ч) + `presented_at` (идемпотентность) +
   `round_id` (гашение раундов).
2. `backend/questions/` (или расширить `backend/tasks/`): роутер §10.2 —
   GET /v1/petrushka/questions (свои — любой, все — isManager; помечает
   presented_at при первом фетче; просроченные asked → expired лениво),
   POST (агент), PATCH /:id (answer|defer — с проверкой «не expired»).
3. **Expire-джоба** (Р5): `deploy/systemd/agropilot-questions-expire.{service,timer}`
   по образцу meteo (ежечасно, DEFAULT_TZ); asked c expires_at < now →
   expired. Просроченные не попадают в обучающие сигналы Q-метрик (M9).
4. **Гашение раунда**: определение «раунда ПЕТРУШКИ» — зафиксировать в §41
   (рекомендация: round_id = запуск цикла myday-digest; старт нового раунда
   гасит asked предыдущего → expired(round_closed)).
5. Фронт: карточки вопросов в чате ПЕТРУШКИ; дедуп по question.id —
   presented_at с бэка + localStorage-кэш показанных id на рестарте сессии.
6. CONTRACTS §41: TTL, идемпотентность, гашение, ленивое истечение.
Верификация DoD: рестарт страницы — вопрос не дублируется (ручная проверка +
pytest на presented_at); вопрос старше TTL не попадает в сигнал Q-метрики
(pytest на выборке); новый раунд гасит старые asked (pytest).

### Параллельно (документ, код после порога B→A)

#### О5 · RFC «фамильяр ↔ ядро» (S)
Текущее: run_logs/agent_cards есть; **Q-метрики M9 не определены нигде** —
RFC обязан начать с их формализации (иначе «критерии готовности к A» из §5
ТЗ не с чем связать).
Шаги: 1) `docs/RFC_MAILBOX.md` — сущность message {id, from_agent, to_agent|
'CORE', kind, payload, status, created_at}; аудит через существующие
`run_logs`/actor_name (M6); протоколы delegation/call/artifact-return;
каждый переход — запись в аудит. 2) Раздел «Q-метрики M9»: определение,
пороги, объёмы, открывающие реализацию (вход для ROADMAP). 3) Ссылка из
ROADMAP.md, секция-заглушка в CONTRACTS (без номера, «после B→A»).
DoD: RFC согласован заказчиком, сохранён в docs/, ссылка из ROADMAP. Код
фамильяров не пишем до прохождения порога B→A (риск ТЗ §6).

### После M12

#### О6 · Telegram-канал ПЕТРУШКИ (M)
Текущее: см. Р6; sendMessage-хелперы существуют в myday/content — вынести
общий TG-клиент при реализации. `backend/channels` (публикации §21) и
медиа-мониторинг (§20/§34) — отдельные контуры, не трогаем.
Шаги:
1. **Отдельный бот ПЕТРУШКИ** (D7): новый токен, webhook-режим.
2. **Миграция**: `channel_bindings` {user_id, channel='telegram', chat_id,
   verified_at, notify_mask(digest|questions|insights)}; привязка — команда в
   боте `/start <код>` + подтверждение в вебе (чтобы чужой chat_id нельзя
   было привязать себе).
3. `POST /v1/telegram/webhook`: сверка secret-token (заголовок);
   входящие только от привязанных chat_id → orchChat от имени пользователя;
   непривязанные — ignore + журнал. Session-нить `<user_id>:telegram:<chat_id>`
   — как `round_id`/context_ref в agent_questions и meta в run_logs (единый
   контур ответов с веб-чатом).
4. Исходящие по notify_mask (opt-in): digest (myday-digest), agent_questions
   (со ссылкой на ответ в логе), accepted-insights; при недоставке — повтор
   в следующем цикле (риск ТЗ §6).
5. CONTRACTS §42: channel_bindings, webhook, notify_mask, session-ключ;
   флаг TELEGRAM_READY в §6.
Верификация DoD: digest уходит только включившим mask; текст от постороннего
chat_id не попадает в orchChat (журнал ignore); ответ на вопрос из TG виден
в логе agent_questions и в вебе (единый контур).

---

## 4. Изменения CONTRACTS.md (сводка)
- §6: + TELEGRAM_READY (и заведение KNOWLEDGE_READY/UX_READY в `js/api.js`
  по мере реализации вех — сейчас их во фронте нет вовсе).
- Новые секции (номера — следующие свободные, Р1): §39 О1, §40 О2, §41 О3,
  §42 О6. Существующие §8–§10 не правим; в §40 даём маппинг на фактическую
  модель sources (Р2), в §39/§41 — фактические имена эндпоинтов (Р4).
- ROADMAP.md: ссылка на RFC О5 после его согласования.

## 5. Порядок исполнения
1. **Этап 0 (сразу)**: О7.1 AGENTS.md → О7.2 CodeQL → О4 (полностью);
   О7.3 argon2 — после утверждения D6.
2. **M10**: О2 (миграция 036 → реестр → rss/arxiv → §40).
3. **M11**: О1 (после D4/D5: миграция → ingest → orchChat → фронт → §39).
4. **M12**: О3 (миграция → роутер → expire-таймер → фронт → §41).
5. **Параллельно**: О5 RFC (начать с Q-метрик).
6. **После M12**: О6 (бот → миграция → webhook → push → §42).
Каждый блок завершается: DoD-верификация → commit (сообщение на русском) →
обновление CONTRACTS → сквозной прогон `scripts/acceptance_test.py` на сервере
перед продом.

## 6. Решения, требующие утверждения заказчиком (до правок)
- **D1** Маппинг verified-only → `status='active' AND active=true` (Р2), без
  возврата к §8-статусам. [рекомендую]
- **D2** Канонический набор `sources.type`: код (012) или БД (017);
  рекомендация — `news/telegram/site/rss` + `connector`-ключ реестра.
- **D3** orchChat = новый `POST /v1/orchestrator/chat` (фронт готов),
  `/v1/assistant/ask` не меняется.
- **D4** Эмбеддинги: (а) fastembed локально [рекомендую] или (б) внешний API.
- **D5** Установка на сервер: Qdrant (docker), rapidocr (onnx).
- **D6** argon2-миграция auth (прозрачный перехэш при логине) — правка
  auth-зоны.
- **D7** Отдельный Telegram-бот для канала ПЕТРУШКИ (webhook); JARVIS_MONITOR
  остаётся на polling.
- **D8** Expire О3: systemd-таймер + ленивый TTL, без планировщика в BFF.

## 7. Риски (дополнение к §6 ТЗ)
- О1 ломает дисциплину «7 пакетов / stdlib» — расширение требований
  заморозить списком из блока О1, дальше не расти.
- Конфликт код/БД по типам sources (Р3) — живой баг уже сейчас; закрыть
  миграцией в О2 до любых новых источников.
- Q-метрики M9 не формализованы — без них RFC О5 и правило «не уходить в A»
  не проверяемы; формализация — первый пункт О5.
- «Раунд ПЕТРУШКИ» не определён в текущей механике — определение в §41
  является проектным решением (D8-соседнее), требует согласования.
