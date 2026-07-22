## 12.5 Frontend-интеграция

Frontend использует отдельную коллекцию `M.strategyTasks`; существующий одиночный объект `M.strategy` и его `GET/PUT /v1/strategy` не заменяются и не смешиваются со стратегическими задачами.

В `js/mock.objects.js` пустая и mock-модели получают `strategyTasks: []`. В `js/api.js` добавляются feature flag `STRATEGY_TASKS_READY` и методы `loadStrategyTasks()`, `createStrategyTask(data)`, `updateStrategyTask(id, data)`, `deleteStrategyTask(id)` для `/v1/strategy/tasks`.

`app.objects.js::_loadAllData()` загружает стратегические задачи вместе с остальными BFF-данными. Результат должен быть учтён во всех связанных местах: `Promise.all`, destructuring, проверке `allEmpty`, `apiData` и присвоении `this.M.strategyTasks`. Ошибка загрузки не должна незаметно подменять production-данные mock-снимком.

Текущий legacy-код `directions[]` не является моделью `strategy_task` и не расширяется в рамках Блока C.

## 12.6 Контекст ПЕТРУШКИ

`owlContext()` дополняется полем `strategyTasks`, содержащим только задачи со `status='active'`. Для каждой задачи в контекст передаются как минимум `id`, `title`, `owner_id`, `monitoring_focus`, `linked_scenario`, `priority` и `status`.

`monitoring_focus` используется ПЕТРУШКОЙ как набор фокусов мониторинга. Неактивные задачи в рабочий контекст не попадают. Отсутствие активных стратегических задач возвращает пустой массив и не нарушает существующий route/object-контекст.

## 12.7 Границы MVP

В scope Блока C входят: таблица и ORM-модель `strategy_tasks`, миграция, CRUD API, валидация, RBAC manager/admin на запись, frontend-загрузка в `M.strategyTasks` и инжект активных задач в `owlContext()`.

Вне scope: замена операционных `tasks`, переработка существующего `strategy_main`, расширенная карточка из Приложения A, новый lifecycle сверх `active|inactive`, автоматическое создание целей или операционных задач, а также рефакторинг legacy `directions[]`.

## 12.8 Definition of Done

Блок C принят, если одновременно выполнено следующее:

1. Миграция создаёт `strategy_tasks` по §12.1 и проходит на PostgreSQL без изменения существующей таблицы `strategy`.
2. Backend предоставляет согласованный CRUD `/v1/strategy/tasks` в конверте `{ok,data}`, использует `AsyncSession`, `Depends(get_db, get_current_user)` и зарегистрирован под `/agropilot/api/v1`.
3. Валидация и RBAC соответствуют §12.3–12.4; чтение доступно авторизованному пользователю, запись — только manager/admin.
4. Frontend загружает данные через `AGL.loadStrategyTasks()` в `M.strategyTasks` и не подменяет их `M.tasks` или `M.strategy`.
5. `owlContext()` получает только active-задачи и их `monitoring_focus`; inactive-задачи исключены.
6. Тесты покрывают CRUD, 401/403, 404, validation errors, фильтрацию active/inactive и frontend smoke-путь загрузки.
7. Проверены `git diff --check`, импорт приложения, регистрация router и raw HTTP-ответы; существующие `/v1/strategy` и route/object-контекст не регрессировали.
