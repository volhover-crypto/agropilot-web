# HANDOVER — AgroPILOT / A PILOT (АгроЭлемент). Перенос состояния в новую сессию
Дата: 2026-07-08 · Репозиторий: github.com/volhover-crypto/agropilot-web (ветка master)

## 0. Статус
- Репозиторий создан и наполнен (подтверждено на github.com и github.dev): assets/, css/, js/, index.html. 1 commit (0434555).
- Ветка по умолчанию: master (рекомендовано унифицировать на main — не сделано).
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
- Ветка master вместо main.

## 7. Следующий шаг (ожидает решения пользователя)
Старт правок кода: (а) M2+опечатки (быстро/безопасно), либо (б) M4 стратегия-сценарии (фундамент), либо (в) сначала ROADMAP.md/ТЗ.md как формальный ШАГ-1.

## 8. Как продолжить в новой сессии
1. Вкладка github.dev: vscode.dev/github/volhover-crypto/agropilot-web (файлы читаются).
2. Быстрое чтение кода: raw.githubusercontent.com/volhover-crypto/agropilot-web/master/js/<файл>.
3. Первое действие: прочитать этот HANDOVER + при необходимости перечитать js/app.objects.js.

## 9. Журнал прогресса (новая сессия 2026-07-08)
- ШАГ-1 оформлен: добавлены ROADMAP.md и ТЗ.md в корень (коммит docs: add ROADMAP.md and ТЗ.md — formal Step-1).
- M2.1 [x]: опечатка 'Новый пект' → 'Новый проект' в js/app.objects.js (addProject, стр.540). Единственное вхождение в коде (проверено поиском). Коммит fix(M2.1).
- Следующие подшаги M2 (кандидаты): TODAY-хардкод → вычисляемая дата; stub() → реальные вьюхи; демо-логин index.html → убрать.
- Метод работы: атомарные шаги, отдельный коммит на подшаг, документирование здесь после каждого.
- M2.2 [x]: TODAY-хардкод '2026-06-24' → new Date().toISOString().slice(0,10) в js/mock.objects.js (стр.5, внутри window.MOCKO). Демо-даты сида (inbox/tasks и т.п.) не тронуты (DEV_MOCK). Коммит fix(M2.2).
- M2.3 [x]: убран демо-логин в index.html (блок loginModal): удалён предзаполненный value="Александр" и placeholder="Александр" → placeholder="Логин"; удалена подсказка «Демо: Александр / test». Механизм auth (AGL.login/doLogin) не тронут — унификация в M8. Коммит fix(M2.3).
- M2.4 [x]: stub()-аудит (js/app.objects.js). Факт: все реальные маршруты render() (dashboard/inbox/goals/projects/kanban/clients/deals/tasks/packages/artifacts/monitoring/content/team/graph/settings и карточки) уже имеют реальные вьюхи; вьюх-недоделок («scoro/в разработке/TODO») нет, пустые данные — через empty(). Из 6 вызовов stub() 5 — легитимные guard’ы «объект не найден» (vGoal/vProject/vTask/vClient/vDealCard) — оставлены. Сделано: fallback в render() (стр.426) this.stub('Раздел не найден') → аккуратная 404-вьюха (card + кнопка data-go="myday:" «На главную»). Коммит feat(M2.4). Пункт §4 «stub() → реальные вьюхи» фактически закрыт (крупной работы не требовалось).
- M2.5 [x]: введён единый флаг window.DEV_MOCK в js/mock.objects.js (перед window.MOCKO, стр.5): window.DEV_MOCK = (typeof window.DEV_MOCK==='boolean') ? window.DEV_MOCK : true. Поведение НЕ изменено (default true — демо-режим сохранён, внешнее значение не перезатирается). Коммит feat(M2.5). Следующее (отдельными подшагами, ждёт решения): M2.6 — завязать инициализацию this.M/fallback на DEV_MOCK (при false — не подставлять MOCKO, показывать empty()); M2.7 — signals/owlSuggestions за DEV_MOCK. petReply→orchChat вынесен в M5 (не M2).
- Сессия 2026-07-09. Решение по M2.6: приоритет источников — вариант 2 (restore()/localStorage остаётся как кэш, но MOCKO не подмешивается при DEV_MOCK=false).
- M2.6-a1 [x]: добавлен window.EMPTY_MODEL в js/mock.objects.js (после DEV_MOCK, перед MOCKO). Пустой скелет той же формы, что MOCKO: справочники STAGES/NEED/IND/SRC_TYPES и структурные strategy/agentConfig сохранены в пустой форме (на них опираются селекты/фильтры/канбан), все данные-коллекции пустые → вьюхи уйдут в empty(). Коммит feat(M2.6-a1). Поведение не изменено (EMPTY_MODEL пока не используется; подключение — в M2.6-a).
- M2.6-a [x]: в js/app.objects.js (appObjects, стр.6) M: window.MOCKO → M: (window.DEV_MOCK ? window.MOCKO : window.EMPTY_MODEL). Коммит feat(M2.6-a).
- M2.6-b [x]: в init() блок «seed истории по сделкам» (deals.forEach + его console.log) обёрнут в if (window.DEV_MOCK) { ... }. Второй сид истории — для API-данных (внутри loadFromAPI().then) — НЕ тронут (это реальные данные, не mock). Коммит feat(M2.6-b).
- M2.6-c [x]: в loadFromAPI() ветка allEmpty разведена по DEV_MOCK: при true — как раньше (оставить мок, apiMode=false); при false — не откатываться на MOCKO, оставить пустое состояние (empty-вьюхи), apiMode=true, return false. Коммит feat(M2.6-c).
- Итог M2.6: default DEV_MOCK=true — поведение демо-режима НЕ изменено. При DEV_MOCK=false — нет демо-сида MOCKO, пустые empty-вьюхи. Приоритет источников — вариант 2 (restore() как кэш). ОСТАЁТСЯ РИСК §6: restore() выполняется до loadFromAPI() — при DEV_MOCK=false старый демо-слепок из localStorage (agropilot_data_v1) может подменить пустое состояние; полное устранение (очистка/игнор restore при !DEV_MOCK) — кандидат M2.6-d, ждёт решения. Следующее: M2.7 (signals/owlSuggestions за DEV_MOCK).
- M2.7 [x]: signals/owlSuggestions за DEV_MOCK. Анализ: в _loadAllData() этих двух источников нет (BFF их не отдаёт), инициализация уже пустая в проде (M2.6-a: EMPTY_MODEL). Единственный чисто демо-генератор — srcScan(id) (кнопка «Проверить» в мониторинге): фабрикует фейковый signal + HINT owlSuggestion. Сделано: в srcScan добавлен guard if (!window.DEV_MOCK) { toast('Скан через BFF, демо-генерация отключена'); return; } — в проде не фабрикуем mock-сигналы (живой скан — задел M5/BFF). Коммит feat(M2.7). Поведение при default DEV_MOCK=true не изменено.
- ОСОЗНАННО НЕ тронуты (это M5, не M2): petReply() — эвристический движок (petReply→orchChat); signalAction()/cliAddModal()/dealSuggestPackage() — генерация HINT-owlSuggestions в ответ на РЕАЛЬНЫЕ действия пользователя (создание клиента/сделки) — это Level-2 HINT-движок ПЕТРУШКИ, тот же класс, что petReply, уйдёт в M5. Пункт §4 «signals/owlSuggestions из mock» по M2 закрыт (демо-сид и демо-генерация за флагом).
- Состояние: M2.6 (a1/a/b/c) и M2.7 внесены в master, несохранённых изменений нет. Открытые кандидаты (ждут решения): M2.6-d (restore() при !DEV_MOCK), M8-хардненинг, M5 (ПЕТРУШКА-непрерывная).
- M2.6-d [x]: завершение M2. В js/app.objects.js, init() (стр.270) вызов restore() обёрнут в if (window.DEV_MOCK) this.restore(); — localStorage-кэш (agropilot_data_v1) восстанавливается только в демо-режиме. При DEV_MOCK=false старый демо-слепок больше не подменяет пустое прод-состояние (риск §6 закрыт). Сам restore() не тронут; ключ localStorage НЕ очищается (необратимых действий нет). Решение — опция 1 (игнор restore() при !DEV_MOCK), согласовано с вариантом 2 M2.6. Коммит fix(M2.6-d). При default DEV_MOCK=true поведение не изменено. ВЕХА M2 ЗАКРЫТА (M2.1–M2.7 + M2.6-d).
- M6/Patch B [x]: аудит действий (actor_name в deal.history). Реализовано 4 атомарными коммитами: M6-a — logDeal(d,kind,text,actor), в запись истории добавлен actor_name: actor || 'Система' (обратно совместимо). M6-b — actor='ПЕТРУШКА' для 5 ИИ-вызовов (owlApply task/stage/package + 2 artifact). M6-c — actor='Оператор' для 11 пользовательских вызовов (moveDeal DnD, 5× групповые, task-завершена, pkg→ready, pkg-черновик, 2× из входящих). Всего 16 вызовов проброшены (проверено: 5×'ПЕТРУШКА' + 11×'Оператор'). M6-d — вывод автора: objActivity пробрасывает actor: h.actor_name в событие; vTimeline рендерит ${it.actor ? ' · '+esc(it.actor) : ''} после текста (старые записи без actor не ломаются). Коммиты feat(M6-a..d). ОГРАНИЧЕНИЕ: в state нет текущего пользователя (this.M.me/AGL.user отсутствуют) — поэтому пользовательские действия атрибутируются обобщённо 'Оператор'; реальная привязка к залогиненному имени — задел M8 (когда auth начнёт отдавать имя). Главный пункт §6 (actor_name в deal.history) ЗАКРЫТ.
- **M8 Харднинг (реальный actor) [x]**: закрыт задел M6/Patch B «обобщённый Оператор». 3 атомарных коммита: M8-a — AGL._decodeUser(token) декодирует JWT-payload (base64url) в AGL.user {id,name} по цепочке name/full_name/login/username/sub; заполняется в _saveToken и initAuth, очищается в logout. M8-b — this.currentUser (реактивное поле state) заполняется из AGL.user в loadFromAPI после initAuth. M8-c — все 11 пользовательских logDeal: 'Оператор' → this.currentUser?.name || 'Оператор' (вызовы 'ПЕТРУШКА' и 'Система' не тронуты). Fallback: нет токена/имени → 'Оператор', поведение прежнее. M8-d — регресс-проверка vTimeline: правок не требуется (логика из M6-d безопасна к любой строке actor). Коммиты feat(M8-a..c). Задел M6 «реальный actor из auth» ЗАКРЫТ по существу. Ограничение: имя берётся из JWT-payload; если бэк не кладёт имя в токен — задел на /v1/auth/me (вариант B).