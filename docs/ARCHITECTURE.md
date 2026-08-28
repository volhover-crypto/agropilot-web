# AgroPILOT — Полная архитектура системы (v1.0, 2026-08-25)

> Документ для подключения сторонней модели-кодера / нового разработчика.
> Продакшн: **https://mdked.hlab.kz/agropilot/**
> Хост: mdked.hlab.kz (KVM, AMD EPYC 4 vCPU, 7.7 GB RAM, Ubuntu)

---

## 1. Общая схема

```
Браузер ──HTTPS──> nginx (:443, mdked.hlab.kz)
                      │
                      ├─ /agropilot/        → статика /opt/agropilot-web/ (SPA: index.html + JS)
                      ├─ /agropilot/api/    → proxy_pass http://127.0.0.1:5560/agropilot/api/
                      ├─ /agropilot/files/  → статика /opt/agropilot-data/artifacts/ (артефакты)
                      └─ /                  → 302 redirect на /agropilot/

FastAPI BFF (:5560, localhost only) ──SQLAlchemy async──> PostgreSQL localhost:5432/db agropilot
Telegram Ingest (отдельный процесс) ──> тот же backend/API
Mock Server (dev)   ──> мок-данные для UI без БД
```

## 2. Компоненты и сервисы

| Компонент | systemd unit | Что делает | Где код |
|---|---|---|---|
| Backend (BFF) | `agropilot-backend.service` | FastAPI + Uvicorn, `backend.main:app`, 127.0.0.1:**5560** | `/opt/agropilot-web/backend/` |
| Telegram ingest | `agropilot-tg.service` | Приём данных из Telegram | `/root/agropilot_bff_new/tg_ingest.py` |
| Mock server | `agropilot-mock.service` | Dev-мок API | `/root/.openclaw/workspace/projects/agropilot/mock_server.py` |
| Nginx | `nginx.service` | Роутинг + TLS | `/etc/nginx/sites-enabled/agropilot-web` |

Статус проверить: `systemctl status agropilot-backend agropilot-tg agropilot-mock`
Логи: `journalctl -u agropilot-backend -n 50`, а также `/var/log/agropilot-bff.log`, `/var/log/agropilot-tg.log`

## 3. Главный репозиторий

- **GitHub:** `https://github.com/volhover-crypto/agropilot-web`
- **Локальная копия (прод):** `/opt/agropilot-web/`
- Ветка: **main**. `master` удалена 2026-07-12 (тег `legacy/master` сохранён).
  Стиль коммитов: conventional (`feat(backend): ...`, `docs(contract): ...`)
- Python-окружение: `/opt/agropilot-web/venv` (fastapi 0.139, uvicorn, sqlalchemy[asyncio] 2.0, asyncpg, pydantic 2.x — полный список в `requirements.txt`)

### Структура /opt/agropilot-web/

```
index.html            — входная точка SPA
js/
  api.js              — клиент API (все вызовы /agropilot/api/)
  app.objects.js      — модели объектов фронтенда
  mock.objects.js     — мок-данные (работа без бэкенда)
  alpine.min.js       — Alpine.js (реактивность UI)
css/                  — Tailwind CSS (prebuilt варианты)
assets/               — иконки, favicon
backend/
  main.py             — точка входа FastAPI
  common/deps.py      — DATABASE_URL (PostgreSQL localhost:5432/agropilot), engine
  common/errors.py    — единая обработка ошибок
  <domain>/           — доменные модули, каждый: routes.py + models.py:
      team, clients, deals, leads, packages, tasks,
      strategy_tasks, goals, calendar, content,
      artifacts, sources, strategy, versions,
      monitoring (§17, read-only), catalog (§18, read-model без своих таблиц)
  migrations/         — миграции схемы
docs/                 — эта папка
CODER_BRIEF.md        — краткий бриф для кодера (читать первым!)
HANDOVER.md           — handover-заметки
CONTRACTS.md          — КОНТРАКТЫ API (источник правды по эндпоинтам)
ROADMAP.md, ROADMAP_M10.md, ТЗ.md — планы и техзадания
requirements.txt
venv/                 — не редактировать, пересоздаётся из requirements.txt
```

### База данных
- PostgreSQL 16, `localhost:5432`, база `agropilot` (переопределяется env `DATABASE_URL`).
- Доступ через SQLAlchemy async engine (`backend/common/deps.py`).
- Артефакты файлов лежат НЕ в БД: `/opt/agropilot-data/artifacts/` (раздаётся nginx как `/agropilot/files/`).

## 4. Смежные репозитории и папки (не прод, но связаны)

| Путь | Репозиторий | Назначение |
|---|---|---|
| `/root/agropilot_bff_new/` | `github.com/volhover-crypto/agropilot_bff_new` | BFF v2-эксперименты: ai_engine.py, llm_router.py, bulk_engine.py, goal_formula.py, graph_engine.py; SQL-миграции RBAC (002, 003); tg_ingest.py (прод!) |
| `/UI/agropilot_ui/` | — | Старый UI-прототип (index.html, UI_SPEC.md) — только история |
| `/root/.openclaw/workspace/projects/agropilot/` | — | Mock server, `001_init_agropilot.sql`, интеграционные скрипты |
| `/root/projects/agropilot/` | — | Legacy: src/sql/logs/backup |
| `/root/vault/agropilot/` | — | Заметки/доки в vault |
| `/root/PILOT_ISHODNIKI/` | — | Исходные ТЗ и отчёты (TZ_AgroPILOT_OPENCLAW.md и др.) |

## 5. Инструкция для сторонней модели-кодера

### Порядок чтения (обязательный)
1. `/opt/agropilot-web/CODER_BRIEF.md`
2. `HANDOVER.md`
3. `CONTRACTS.md` — контракты API, источник правды
4. `ROADMAP.md` (+ `ROADMAP_M10.md`) и `ТЗ.md`
5. `backend/main.py` → `common/deps.py` → нужный доменный модуль
6. `js/api.js` — как фронтенд ходит в API

### Правила работы
1. **CONTRACTS.md меняется вместе с кодом**: любой новый/изменённый эндпоинт = обновление контракта тем же коммитом.
2. **Conventional commits** (`feat(backend):`, `fix(frontend):`, `docs(contract): ...`).
3. **Никогда не коммитить секреты**: токены ботов, PAT GitHub, пароли БД. Git remote содержит embedded token — в документах/логах указывать URL без токена.
4. **Не трогать**: `venv/`, n8n workflows, другие сайты на сервере (jarvis hub, vikunja, zvec).
5. **Restart сервисов** (`systemctl restart agropilot-*`) выполняет оператор/Jarvis после проверки изменений — кодер сообщает «готово к деплою», не рестартует сам.
6. Проверка после изменений (локально):
   ```bash
   cd /opt/agropilot-web
   venv/bin/python -c "from backend.main import app"   # импорт без ошибок
   curl -s http://127.0.0.1:5560/agropilot/api/<endpoint>
   ```

### Деплой (выполняет оператор)
```bash
cd /opt/agropilot-web && git pull
sudo systemctl restart agropilot-backend
journalctl -u agropilot-backend -n 20 --no-pager
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5560/docs   # 200 = OK
curl -s -o /dev/null -w "%{http_code}" https://mdked.hlab.kz/agropilot/  # 200 = OK
```

## 6. Известные особенности

- Фронтенд — serverless SPA на Alpine.js без сборщика; Tailwind prebuilt (не менять на CDN-версию без обсуждения).
- `mock.objects.js` позволяет работать UI без бэкенда — при изменении моделей объектов обновлять оба файла (app.objects.js и mock.objects.js).
- Домен: Let's Encrypt до ~17.08.2026, HSTS включён.
- Порт 8080 провайдером заблокирован — все внешние сервисы только через nginx reverse proxy.

---
*Сгенерировано Джарвисом 2026-08-25 по живому состоянию сервера (systemd, nginx, git).*
