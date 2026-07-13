# PERPLEXITY SESSION HANDOFF — AgroPILOT

> Вставь этот текст целиком в первое сообщение новой сессии Perplexity.
> Агент прочитает его и сразу готов продолжать без потери контекста.

---

## Роли команды

| Роль | Агент | Зона |
|------|-------|------|
| Оркестратор | Пользователь (volhover-crypto) | Решения, приоритеты, приёмка |
| Архитектор / Диспетчер | Perplexity | Декомпозиция, брифинги, коммиты в репо, верификация |
| Серверный агент | OpenClaw | SSH, psql, nano/vim, деплой, Console-браузера |

**Репозиторий:** https://github.com/volhover-crypto/agropilot-web (ветка `main`)
**Прод:** https://mdked.hlab.kz/agropilot/
**Источник правды:** `HANDOVER.md` — читать первым действием.

---

## Система (1 абзац)

**AgroPILOT** — объектно-ориентированный агро-B2B рабочий стол для малой команды. Стек: Alpine.js (без сборки), ванильный JS, innerHTML-рендер, hash-роутинг, FastAPI/uvicorn на `127.0.0.1:5555`, PostgreSQL `agropilot@localhost:5432`, nginx, SSL Let's Encrypt.

---

## ТОЧКА ОСТАНОВКИ — 13.07.2026 17:51 МСК

### ✅ Закрыто сегодня

| # | Что | Кто | Коммит / статус |
|---|-----|-----|-----------------|
| Дефект #1 P0 | `#view` пустой — исправлено: синтаксическая ошибка `};` перед `vStrategy()` + `owlPending() \|\ []` guard | OpenClaw (на сервере) | **не в репо** — нужен git push |
| Дефект #2 P0 | `bindView()` падал молча — обёрнут в try/catch | OpenClaw (на сервере) | **не в репо** — нужен git push |
| index.html | auth guard обёрнут в `DOMContentLoaded` | OpenClaw (на сервере) | **не в репо** — нужен git push |
| seed_prod.sql | Добавлены team(5), clients(5), goals(3), deals(8), tasks(8) | Perplexity | [коммит 5c9dc3b](https://github.com/volhover-crypto/agropilot-web/commit/5c9dc3bab81fece3257fd4659780ca586e30d983) ✅ |

### ⏳ Не выполнено — первое задание завтра

**OC-3 (OpenClaw) — СРОЧНО, первым делом:**
```
cd /opt/agropilot-web
git add js/app.objects.js index.html
git commit -m "fix(issue#1-1+2): syntax fix vStrategy, owlPending guard, bindView try/catch, auth DOMContentLoaded"
git push origin main
Прислать: git log --oneline -3
```

**OC-4 (OpenClaw) — после OC-3:**
```
psql -U postgres -d agropilot \
  -f /opt/agropilot-web/backend/seed/seed_prod.sql
Прислать: SELECT COUNT(*) FROM deals; SELECT COUNT(*) FROM tasks; SELECT COUNT(*) FROM clients;
```

**Верификация Console (пользователь):**
Открыть https://mdked.hlab.kz/agropilot/ → F12 → Ctrl+Shift+R
Ожидаемая картина:
```
[AgroPILOT] appObjects.js loaded, MOCKO: object
[AgroPILOT] init() called
[AgroPILOT] deals count: 8
[AGL] loadFromAPI: token? NO
[AGL] no token, showing login
```
Красных строк — ноль.

### 🔴 Открытые дефекты

**Дефект #3 P1** — продовая БД пустая (seed не применён). Решение: OC-4 выше.

**Дефект #4 P1** — `POST /agropilot/api/v1/auth/login → 404 Not Found`. Причина: auth-роутер **не существует** в `backend/main.py`. В репо подключены только: calendar, deals_versions, skills, strategy. Auth-модуль нужно создать с нуля.

---

## Следующий спринт (после закрытия #3 и #4)

По [ROADMAP.md](https://github.com/volhover-crypto/agropilot-web/blob/main/ROADMAP.md) — активная веха **M9 (клиентская часть)** плюс старт **Этап-2 (M10)**: реестр источников, knowledge base, agent_questions.

**Дефект #4 (auth) — план:**
1. Создать `backend/auth/routes.py` — эндпоинт `POST /auth/login` (JWT или simple token)
2. Подключить в `backend/main.py`
3. Обновить `js/api.js` — `AGL.login()` метод

---

## Продовая архитектура

```
Frontend (static) : /opt/agropilot-web/ → nginx alias
Backend (FastAPI)  : 127.0.0.1:5555 (uvicorn, ручной запуск, systemd не настроен)
Database          : PostgreSQL, база agropilot, localhost:5432, пользователь postgres
SSL               : Let's Encrypt, домен mdked.hlab.kz
URL               : https://mdked.hlab.kz/agropilot/
```

---

## Правила агента

1. Читай `HANDOVER.md` первым действием.
2. Правки в прод — только с явного подтверждения пользователя.
3. Атомарные коммиты: `fix(issue#N-M)` / `feat(...)` / `docs(...)`.
4. Обновляй `HANDOVER.md` после каждого закрытого дефекта.
5. Issue #1 закрывает только пользователь после QA.
6. Брифинги для OpenClaw — через пользователя, не напрямую.
