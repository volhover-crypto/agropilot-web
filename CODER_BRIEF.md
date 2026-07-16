# CODER BRIEF — issue#1-3 + systemd (2026-07-16)

> Для агента-кодера. Сразу приступай к действиям. Отчитайся по каждому шагу.

---

## Статус issue#1

| Дефект | Статус | Коммит |
|---|---|---|
| #1-1 — `#view` не рендерил (`bindView` не был определён) | ✅ ЗАКРЫТ | `31ca92db` |
| #1-2 — ПЕТРУШКА не отвечала (`owlRender`/`owlAsk` не были определены) | ✅ ЗАКРЫТ | `a63e68c0` |
| #1-3 — seed-данные не загружены в PostgreSQL | 🔴 **ТВОЯ ЗАДАЧА** | — |

---

## Задача #1-3 — запустить SQL seed на проде

### Симптом

Три эндпоинта возвращают пустые массивы:

```
GET /agropilot/api/v1/calendar?from=2026-07-01  →  {"data":[]}
GET /agropilot/api/v1/team/skills               →  {"data":[]}
GET /agropilot/api/v1/strategy                  →  {"data":{"scenarios":[]}}
```

### SQL-скрипт уже готов в репозитории

Файл: [`backend/migrations/003_seed_calendar_skills_strategy.sql`](https://github.com/volhover-crypto/agropilot-web/blob/main/backend/migrations/003_seed_calendar_skills_strategy.sql)  
Коммит: `c6ec10cc` (запущен 2026-07-16)

Скрипт содержит:
- **5 записей** `calendar_events` (EV1–EV5) — `ON CONFLICT (id) DO NOTHING`
- **7 записей** `team_skills` (SK1–SK7) — `ON CONFLICT (id) DO NOTHING`
- **1 upsert** `strategy` (strategy_main + SC1–SC3 JSONB) — `ON CONFLICT (id) DO UPDATE`

Скрипт **идемпотентный** — повторный запуск безопасен.

### Твои шаги

**Шаг 1 — подтянуть репозиторий:**
```bash
cd /opt/agropilot-web && git pull
```
Проверить, что файл есть:
```bash
ls backend/migrations/003_seed_calendar_skills_strategy.sql
```

**Шаг 2 — запустить скрипт:**
```bash
psql -U postgres -d agropilot \
  -f /opt/agropilot-web/backend/migrations/003_seed_calendar_skills_strategy.sql
```
Ожидаемый вывод:
```
INSERT 0 5
INSERT 0 7
INSERT 0 1
```
(если seed уже запускался раньше — `INSERT 0 0`, это норма)

**Шаг 3 — проверить API:**
```bash
curl -s "https://mdked.hlab.kz/agropilot/api/v1/team/skills" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print('skills:', len(d.get('data',[])))"

curl -s "https://mdked.hlab.kz/agropilot/api/v1/calendar?from=2026-07-01&to=2026-07-31" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print('events:', len(d.get('data',[])))"

curl -s "https://mdked.hlab.kz/agropilot/api/v1/strategy" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); sc=d.get('data',{}).get('scenarios',[]); print('scenarios:', len(sc))"
```
Ожидаемый результат:
```
skills: 7
events: 5
scenarios: 3
```

**Шаг 4 — отчитайся пользователю.** Дефект закрывает только пользователь. HANDOVER.md не трогать.

---

## Бонус-задача: перевести backend на systemd

> Выполняй только если шаг 1–3 успешно закрыт. Без согласования с пользователем не выполнять.

### Проблема

Backend uvicorn запущен вручную (не переживёт ребут сервера):
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 5555
```

### Шаги

**Шаг A — создать unit-файл:**
```bash
cat > /etc/systemd/system/agropilot.service << 'EOF'
[Unit]
Description=AgroPILOT Backend
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/agropilot-web
ExecStart=/usr/local/bin/uvicorn backend.main:app --host 127.0.0.1 --port 5555
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

> Если uvicorn установлен в venv, замени путь: `/usr/local/bin/uvicorn` → `/opt/agropilot-web/.venv/bin/uvicorn` или `/home/<user>/.local/bin/uvicorn`.
> Проверить: `which uvicorn`

**Шаг B — активировать и запустить:**
```bash
systemctl daemon-reload
systemctl enable agropilot
systemctl start agropilot
systemctl status agropilot
```

Ожидаемый вывод статуса:
```
● agropilot.service - AgroPILOT Backend
   Active: active (running) ...
```

**Шаг C — проверить что API живой:**
```bash
curl -s http://127.0.0.1:5555/agropilot/api/v1/strategy | python3 -c \
  "import sys,json; print(json.load(sys.stdin).get('ok'))"
# → True
```

**Шаг D — отчитайся:** сообщи пользователю вывод `systemctl status` + результат curl.

---

## Что НЕ делать

- ❌ Не менять исходные файлы (`js/`, `backend/`)
- ❌ Не выполнять DROP/TRUNCATE без явного указания пользователя
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
