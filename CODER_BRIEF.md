# CODER BRIEF — issue#1-3 + systemd (2026-07-17)

> Для агента Comet. Сразу приступай к действиям. Отчитайся по каждому шагу.

---

## Статус issue#1

| Дефект | Статус | Коммит |
|---|---|---|
| #1-1 — `#view` не рендерил (`bindView` не был определён) | ✅ ЗАКРЫТ | `31ca92db` |
| #1-2 — ПЕТРУШКА не отвечала (`owlRender`/`owlAsk` не были определены) | ✅ ЗАКРЫТ | `a63e68c0` |
| #1-3 — seed-данные не загружены в PostgreSQL | 🔴 **ТЕКУЩАЯ ЗАДАЧА** | — |

---

## Две роли: кто что делает

У тебя (**Comet**) нет SSH-доступа к серверу. Работа сплит между двумя:

| Роль | Исполнитель | Что делает |
|---|---|---|
| **Comet** | Браузерный агент | Проверяет API через браузер, читает GitHub, фиксирует результат |
| **Пользователь** | SSH-терминал | Выполняет команды на сервере, вставляет вывод в чат |

**Схема работы:**
1. Comet смотрит API → даёт команду для копирования
2. Пользователь запускает команду в терминале, вставляет вывод в чат
3. Comet читает вывод, проверяет API, фиксирует результат

---

## Шаг 0 — pre-check: проверить состояние до seed

**Comet** — до любых действий открой эти URL в браузере и зафиксируй результат:

```
https://mdked.hlab.kz/agropilot/api/v1/team/skills
https://mdked.hlab.kz/agropilot/api/v1/calendar?from=2026-07-01&to=2026-07-31
https://mdked.hlab.kz/agropilot/api/v1/strategy
```

Если `data.length > 0` во всех трёх — seed уже выполнен, шаги 1–3 пропускать, сразу к бонусу.

---

## Задача #1-3 — запустить SQL seed на проде

### SQL-скрипт уже готов в репозитории

Файл: [`backend/migrations/003_seed_calendar_skills_strategy.sql`](https://github.com/volhover-crypto/agropilot-web/blob/main/backend/migrations/003_seed_calendar_skills_strategy.sql)  
Коммит: `c6ec10cc`

Скрипт содержит:
- **5 записей** `calendar_events` (EV1–EV5) — `ON CONFLICT (id) DO NOTHING`
- **7 записей** `team_skills` (SK1–SK7) — `ON CONFLICT (id) DO NOTHING`
- **1 upsert** `strategy` (strategy_main + SC1–SC3 JSONB) — `ON CONFLICT (id) DO UPDATE`

Скрипт **идемпотентный** — повторный запуск безопасен.

---

### Шаг 1 — Пользователь запускает в терминале

Копируй и выполняй поблочно:

```bash
cd /opt/agropilot-web && git pull
```

```bash
psql -U postgres -d agropilot \
  -f /opt/agropilot-web/backend/migrations/003_seed_calendar_skills_strategy.sql
```

Вставь вывод в чат полностью.

Ожидаемый вывод (first run):
```
INSERT 0 5
INSERT 0 7
INSERT 0 1
```
(если seed уже был раньше: `INSERT 0 0` — это норма)

### Шаг 2 — Comet проверяет API

**Comet** — открой в браузере:
```
https://mdked.hlab.kz/agropilot/api/v1/team/skills
https://mdked.hlab.kz/agropilot/api/v1/calendar?from=2026-07-01&to=2026-07-31
https://mdked.hlab.kz/agropilot/api/v1/strategy
```
Убедись, что `data` уже не пустой. Зафиксируй количество записей в отчёте.

Ожидаемый результат:
```
skills: 7 ✔️
events: 5 ✔️
scenarios: 3 ✔️
```

### Шаг 3 — отчёт

Comet сообщает пользователю результат. Дефект закрывает только пользователь. HANDOVER.md не трогать.

---

## Бонус-задача: перевести backend на systemd

> **Согласовано заказчиком заранее.** Выполняй сразу после успешного шага 0/1/2.

### Проблема

Backend запущен вручную и не переживёт ребут сервера.

### Пользователь выполняет в терминале

**Шаг A — узнать путь к uvicorn:**
```bash
which uvicorn
```
Вставь вывод в чат — Comet подскажет правильный `ExecStart`.

**Шаг B — создать unit-файл** (подставь путь из вывода `which uvicorn`):
```bash
cat > /etc/systemd/system/agropilot.service << 'EOF'
[Unit]
Description=AgroPILOT Backend
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/agropilot-web
ExecStart=<PATH_FROM_WHICH> backend.main:app --host 127.0.0.1 --port 5555
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

**Шаг C — активировать:**
```bash
systemctl daemon-reload
systemctl enable agropilot
systemctl start agropilot
systemctl status agropilot
```
Вставь вывод `status` в чат полностью.

**Шаг D — Comet проверяет API** через браузер:
```
https://mdked.hlab.kz/agropilot/api/v1/strategy
```
Ожидаем ответ: `{"ok": true, ...}`

---

## Что НЕ делать

- ❌ Не менять исходные файлы (`js/`, `backend/`)
- ❌ Не выполнять DROP/TRUNCATE без явного указания
- ❌ Не закрывать issue #1 — это делает только пользователь
- ❌ Не трогать HANDOVER.md

---

## Контекст среды

| Параметр | Значение |
|---|---|
| Сервер | `mdked.hlab.kz` |
| Фронтенд | `/opt/agropilot-web/` |
| Backend | `uvicorn backend.main:app --host 127.0.0.1 --port 5555` |
| PostgreSQL | `agropilot@localhost:5432`, user `postgres` |
| Прод URL | https://mdked.hlab.kz/agropilot/ |
| issue | https://github.com/volhover-crypto/agropilot-web/issues/1 |
