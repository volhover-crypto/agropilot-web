# PERPLEXITY SESSION HANDOFF — AgroPILOT

> Вставь этот текст целиком в первое сообщение новой сессии Perplexity. Агент прочитает его и сразу готов продолжать работу без потери контекста.

---

## Кто я и чем занимаюсь

Я агент Perplexity, работающий в роли **архитектора и технического партнёра** по проекту **AgroPILOT** для заказчика волховер (github: volhover-crypto).

**Репозиторий:** https://github.com/volhover-crypto/agropilot-web (ветка `main`)
**Прод:** https://mdked.hlab.kz/agropilot/
**Источник правды:** `HANDOVER.md` в корне репозитория — **читай его первым действием** в новой сессии.

---

## Система (1 абзац)

**AgroPILOT** — объектно-ориентированный агро-B2B рабочий стол для малой команды, замещающий ERP/CRM/календарь/вики/коммуникации. Стек: Alpine.js (без сборки), ванильный JS, innerHTML-рендер, hash-роутинг, FastAPI/uvicorn на `127.0.0.1:5555`, PostgreSQL `agropilot@localhost:5432`, nginx, SSL Let’s Encrypt.

---

## Текущий статус (на 13.07.2026)

### Этап-1: ✅ по инфраструктуре, ❌ по UI

| Блок | API | UI | Итог |
|---|---|---|---|
| Frontend (загрузка, авторизация, навигация DOM) | — | ✅ | OK |
| Calendar (`CALENDAR_READY`) | ✅ 200, data:[] | 🔴 #view пустой | FAIL |
| Skills (`SKILLS_READY`) | ✅ 200, data:[] | 🔴 #view пустой | FAIL |
| Strategy (`STRATEGY_READY`) | ✅ 200, scenarios:[] | 🔴 #view пустой | FAIL |
| ПЕТРУШКА-агент | — | 🔴 owlBody пустой | FAIL |

### Открыто: [issue #1](https://github.com/volhover-crypto/agropilot-web/issues/1)

**Дефект #1 P0** — `<div id="view"></div>` пустой при клике на любой из 19 разделов (спиннер появляется, active-класс ставится, но рендер не вызывается). Гипотеза: исключение в `AGL.init()` гасит роутер.

**Дефект #2 P0** — `owlBody` пустой после Enter/клика в `owlInput`. Гипотеза: нет bind обработчика или не вызывается `orchChat`/`petReply`.

**Дефект #3 P1** — продовая БД пустая: EV1–EV5, team_skills U3/U5, SC1–SC3 не загружены.

---

## Текущая задача

Провести диагностику и устранить все три дефекта из [issue #1](https://github.com/volhover-crypto/agropilot-web/issues/1) по плану из `OPENCLAW_PROMPT.md`. После — повторный QA-прогон.

---

## Файлы для быстрого старта

| Файл | Назначение |
|---|---|
| `HANDOVER.md` | Полная история сессий, архитектура, вехи M1–M9 |
| `CONTRACTS.md` | API-контракты, схемы, флаги READY |
| `ROADMAP.md` | Дорожная карта Этап-1 и Этап-2 (M10–M12) |
| `OPENCLAW_PROMPT.md` | Системный промпт для агента-исполнителя |
| `js/app.objects.js` | ~3716 стр. ядра: state, resolvers, вьюхи, AGL.init, render |
| `js/api.js` | REST-клиент BFF, feature flags, apiMode |
| `js/mock.objects.js` | MOCKO (seed-данные), DEV_MOCK, EMPTY_MODEL |
| `index.html` | Auth-guard, навигация 4 блока ЖЦ, owlInput/owlBody |
| `backend/main.py` | FastAPI: calendar, skills, strategy роутеры |

---

## Продовая архитектура

```
Frontend (static) : /opt/agropilot-web/ → nginx alias
Backend (FastAPI)  : 127.0.0.1:5555 (uvicorn, ручной запуск, systemd не настроен)
Database          : PostgreSQL, база agropilot, localhost:5432, пользователь postgres
SSL               : Let’s Encrypt, домен mdked.hlab.kz
HTTP → HTTPS      : redirect 302
URL               : https://mdked.hlab.kz/agropilot/
```

---

## Правила для агента в этой сессии

1. **Читай HANDOVER.md первым** действием перед любым действием.
2. **Правки в прод — только с явного подтверждения** пользователя.
3. **Атомарные коммиты**, формат `fix(issue#1-N)` / `feat(...)` / `docs(...)`.
4. **Обновляй HANDOVER.md §12** после каждого закрытого дефекта.
5. **Issue #1 закрывает только пользователь** после повторного QA.
6. **Следующий шаг после issue #1** — старт Этапа-2 (M10): реестр источников, knowledge base, agent_questions.
