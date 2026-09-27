# AGENTS.md — правила работы с репозиторием AgroPILOT (для ИИ-агентов и кодеров)

Жёсткие границы. Этот файл — о том, что нельзя ломать. Человеческая
документация: CONTRACTS.md (контракты API), HANDOVER.md (история передач),
ТЗ.md / ТЗ_ИНТЕГРАЦИЯ_OCTOP.md (задания), ROADMAP*.md (вехи).

## Стек (не переписывать)
- Фронт: Alpine SPA **без сборки** — `index.html` + `js/`, вендоры в `js/vendor/`.
  Tailwind/Pico из локальных файлов, никаких CDN и npm-сборки.
- Бэк: FastAPI BFF (`backend/main.py`), SQLAlchemy async + PostgreSQL, stdlib
  `urllib` для HTTP (внешние HTTP-библиотеки не добавлять без решения заказчика).
- Деплой: `git pull` на сервере `/opt/agropilot-web` (root@mdked.hlab.kz).

## Карта модулей backend/*
- `common/` — deps (DI, get_db/get_current_user), errors, llm (шлюз OpenRouter), tz (таймзоны).
- `auth/` — JWT + пароли (argon2id; legacy-bcrypt проверяется и перехэшируется при логине).
- `team/`, `clients/`, `leads/`, `deals/`, `tasks/`, `goals/`, `calendar/` — операционные контуры.
- `strategy/`, `strategy_tasks/`, `segments/`, `versions/`, `skills` (в versions) — стратегия и навыки.
- `content/`, `channels/`, `packages/`, `artifacts/` — контент-конвейер и публикации (§21).
- `news/`, `sources/`, `monitoring/` — медиа-мониторинг A1 и источники (§20, §13.1).
- `inbound/` — входящие обращения A4 + tg_poller (бот JARVIS_MONITOR, polling).
- `myday/`, `assistant/`, `agents/` — «Мой день», чат-ассистент A7, реестр агентов и run_logs.
- `meteo/` — МИА-метео (запуск systemd-таймерами `deploy/systemd/agropilot-meteo@*.timer`).
- `connectors/` — слой коннекторов источников (§39): реестр, rss/arxiv/cyberleninka, PKCE.
- `questions/` — вопросы агента ПЕТРУШКИ (§40): TTL, идемпотентность, гашение раундов; expire-джоба systemd.
- `knowledge/` — RAG-контур M11 (§41): конвейер документов, чанкинг, эмбеддинги, Qdrant/Memory-стор.
- `orchestrator/` — orchChat (§41.3): knowledge-aware чат с citations и unverified-деградацией.
- `petchannel/` — Telegram-канал ПЕТРУШКИ (§42): webhook, привязка, notify_mask.
- `migrations/` — нумерованные SQL-миграции (следующий свободный номер — в имени файла).

## Ввод контуров О1/О6 на сервере (после подтверждения заказчика)
1. `venv/bin/pip install -r requirements.txt` (+ зафиксировать версии
   fastembed/rapidocr-onnxruntime из вывода pip freeze).
2. Qdrant: docker-контейнер, порт 6333; `QDRANT_URL=http://127.0.0.1:6333` в .env.
3. Миграции 036–039 (psql), systemd: `agropilot-questions-expire.timer`.
4. Telegram (§42): в .env — `PETRUSHKA_TG_BOT_TOKEN`, `PETRUSHKA_TG_WEBHOOK_SECRET`
   (произвольная длинная строка); setWebhook:
   `curl "https://api.telegram.org/bot<TOKEN>/setWebhook" -d "url=https://<host>/agropilot/api/v1/telegram/webhook" -d "secret_token=<SECRET>"`.
   Модель fastembed (мультиязычная MiniLM) скачается при первом эмбеддинге.

## Запреты
1. **Не править `js/mock.objects.js` в прод-режиме** (`DEV_MOCK=false` в
   `index.html` — текущее состояние): мок-данные не должны попадать в прод-ветку.
2. **`esc()` обязателен** для любых пользовательских данных в innerHTML и
   template-literal интерполяциях (`js/app.objects.js`, метод `esc()`).
   Экранируются данные из API/ввода; внутренние константы — на усмотрение.
3. **Прод-деплой — только после явного подтверждения заказчика.** Коммиты в
   `main` ≠ разрешение деплоить. Push без подтверждения запрещён.
4. **Не трогать вендоры** `js/vendor/*`, `css/`, `assets/` кроме явной задачи.
5. **Секреты** (токены, пароли, `.env`) не коммитить; `.env.example` — только
   плейсхолдеры.
6. Новые зависимости — только по решению заказчика (сейчас minimal set,
   см. requirements.txt).

## Слой таймзон (единый, не расползается)
- БД и код — UTC (`timestamptz`, `datetime.now(timezone.utc)`).
- Расписания — только с явной зоной: systemd-таймеры `Europe/Moscow`,
  n8n `GENERIC_TIMEZONE=Europe/Moscow`.
- Конфиг-зона BFF: `DEFAULT_TZ` (по умолчанию Europe/Moscow, см.
  `backend/common/tz.py`); «голое» время без offset в API трактуется как
  DEFAULT_TZ, отдаём всегда ISO 8601 с offset.

## Стиль
- Комментарии и коммиты — на русском; идентификаторы — на английском.
- Контракт ответа API: `{"ok": true, "data": ...}` / `{"ok": false, "error": {code, message}}`.
- Изменения API/схемы — сначала секция в CONTRACTS.md, потом код.
- Тесты — в `tests/` (pytest), прогон перед коммитом: `.venv/Scripts/python -m pytest`
  (локально) или `venv/bin/pytest` (сервер).

## Связка с промпт-файлами
- `COMET_PROMPT.md`, `OPENCLAW_PROMPT.md` — ролевые промпты внешних агентов:
  не синхронизировать с кодом, менять только по заданию.
- `HANDOVER.md` — протокол передач между сессиями; `CODER_BRIEF.md` — бриф
  для кодеров-людей.
