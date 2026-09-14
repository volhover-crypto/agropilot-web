# n8n-воркфлоу A1 — медиа-мониторинг (§20)

Импорт: n8n (docker на прод-сервере) → Workflows → Import from File →
`a1_media_monitor_template.json`, затем заполнить credentials и переменные.

## Что делает шаблон

1. **Schedule Trigger** — раз в час (частота сканирования каждого источника
   берётся из `sources.check_period_min`, воркфлоу лишь запускает цикл).
2. **HTTP Request** — `POST https://mdked.hlab.kz/agropilot/api/v1/news/scan`
   с заголовком `Authorization: Bearer {{$env.AGROPILOT_SERVICE_TOKEN}}`.
   Бэкенд сам обходит источники, дедуплицирует и оценивает релевантность.
3. **On fail** — Telegram-уведомление админу (П.) с текстом ошибки
   (п. 6.5 ТЗ: автоперезапуск + уведомление).

## Переменные окружения n8n

- `AGROPILOT_SERVICE_TOKEN` — access-JWT служебной учётки u7 (§23.2).
  Получение: `POST /v1/auth/login {"login":"u7","password":...}` —
  пароль задаёт оператор через `set_password` (включая u7).
  Токен живёт 60 минут — воркфлоу должен перед запросом делать refresh
  через `POST /v1/auth/refresh` (refresh-токен u7 в `AGROPILOT_SERVICE_REFRESH`).
- `ADMIN_TG_CHAT_ID` — чат администратора для уведомлений о сбоях.

## Статус

Шаблон-каркас: импортируется, но НЕ активировать до реализации эндпоинта
`POST /v1/news/scan` (Этап 2, §20.2) — иначе воркфлоу будет ловить 404.
