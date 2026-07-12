# HANDOVER — AgroPILOT / A PILOT (АгроЭлемент). Перенос состояния в новую сессию
Дата: 2026-07-08 · Репозиторий: github.com/volhover-crypto/agropilot-web (ветка main)

## 0. Статус
- Репозиторий создан и наполнен (подтверждено на github.com и github.dev): assets/, css/, js/, index.html. 1 commit (0434555).
- Ветка по умолчанию: main ✅ (переименовано 2026-07-12, M8: создана ветка main на HEAD d950a860, default branch обновить в настройках GitHub Settings → Branches).
- Ограничение: правки прод-исходников — ТОЛЬКО с явного подтверждения пользователя. Правок кода пока НЕ вносилось; вся работа аналитическая/планировочная (кроме этого файла).

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
M1 Де-IoT/терминология · M2 Устранение заглушек · M3 Перегруппировка в 4 блока (навигация block:1..4) · M4 Стратегия-сценарии (strategy.scenarios[2..4]+indicators; api: loadStrategy/updateStrategy) · M5 ПЕТРУШКА-непрерывная (owlContext=системный агрегат; petSend→orchChat при apiMode; aiDigest по расписанию) · M6 Аудит действий Patch B (actor_name в deal.history + logDeal(d,kind,text,actor) + вывод в vTimeline) · M7 Финучёт/версии артефактов/календарь · M8 Хардненинг (убрать демо-логин, единый esc()/XSS, унификация STAGE_MAP↔vMetrics, ветка main) · M9 Замер навыков (метрики → порог B→A).

## 6. Известные баги/риски (факт)
- Patch B: actor_name в deal.history НЕ реализован (главный пункт доработки).
- Опечатка 'Новый пект'.
- Массовый innerHTML — esc() неединообразно (XSS-риск на реальных данных).
- restore() (localStorage) до loadFromAPI() — приоритет источников не задан (рассинхрон).
- STAGE_MAP из BFF (Проектирование/Выиграна) ≠ фильтры vMetrics (Реализация/Сервис) → конверсия неверна.
- ~~Ветка master вместо main~~ → ✅ ЗАКРЫТ M8 (2026-07-12): ветка main создана на HEAD d950a860, идентична master; сменить default branch: GitHub Settings → Branches → main.

## 7. Следующий шаг (ожидает решения пользователя)
Старт правок кода: (а) M2+опечатки (быстро/безопасно), либо (б) M4 стратегия-сценарии (фундамент), либо (в) сначала ROADMAP.md/ТЗ.md как формальный ШАГ-1.

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
M9-doc [x] · M9-a [x] · M9-b [x] · M9-c [x] — все подшаги завершены и верифицированы.
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

## 11. Журнал прогресса (сессия 2026-07-12)
- **M7 frontend ✅ ЗАКРЫТ** (верифицировано контролёром): `vCalendar()`, `createEventModal()`, `bindView` data-cal-filter/data-create-event, mock EV1–EV5. Верифицированный HEAD: `44ab6c4f1c`.
- **M8 — демо-логин**: аудит index.html подтвердил — демо-логин убран в M2.3; `index.html` чист, хардкодов нет.
- **M8 — ветка main ✅ ЗАКРЫТ**: создана ветка `main` из `master` HEAD `d950a860023184c7d3440985be989bc85a48a950` (2026-07-12). ⚠️ Требуется ручное действие: GitHub Settings → Branches → сменить default branch с `master` на `main`.
- **M8 ✅ ПОЛНОСТЬЮ ЗАКРЫТ**: все 4 пункта выполнены (демо-логин M2.3, esc/XSS, STAGE_MAP↔vMetrics, ветка main).
- **M9 — текущий статус**: M9-doc/M9-a/M9-b/M9-c все закрыты (см. секцию выше). Открыто: SKILLS_READY + loadSkills() в api.js — только после backend-подъёма.
- **Следующий шаг**: анализ M9 клиентской части (что именно остаётся реализовать после backend-подъёма).