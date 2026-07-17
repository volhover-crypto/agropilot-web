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
- **Backend (FastAPI/uvicorn):** `127.0.0.1:5555`, systemd-сервис `agropilot.service` ✅ (переживает ребут)
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
