# n8n-воркфлоу кросспостинга (§46, CONTRACTS.md)

- `pub-publish-core.workflow.json` — движок: свой webhook-триггер
  `POST /n8n/webhook/pub-core` (X-PUB-TOKEN), загрузка поста и активных
  каналов из БД, форматтеры TG/VK, вызовы API платформ, UPSERT результатов.
- `pub-publish-webhook.workflow.json` — внешняя точка:
  `POST https://<host>/n8n/webhook/pub-publish` с заголовком `X-PUB-TOKEN`,
  тело `{"post_id": N}`; вызывает core HTTP-запросом на
  `http://127.0.0.1:5678/webhook/pub-core` (n8n в host network).

В JSON остался один плейсхолдер `__CRED_DB_ID__` / `__CRED_TOK_ID__`
(id credential n8n), заменяется при деплое.

## Инструменты (`tools/`)

- `gen_n8n_pub.py` — генератор обоих JSON (источник истины; правки только
  здесь, затем `python gen_n8n_pub.py`).
- `update_wf.py <core.json> <hook.json>` — обновление обоих workflow на
  сервере: новая версия в `workflow_history` + переключение `versionId` И
  `activeVersionId` в `workflow_entity` (исполняется именно activeVersionId).
- `dryrun_pub.sh` — набор curl-проверок (403/400/404/skipped).
- `last_exec.py [id]` — разбор исполнения n8n (последний узел, ошибка).

## Первый ввод (выполнен 28.09.2026)

1. Миграция `backend/migrations/046_pub_tables.sql`; роль `n8n_pub`
   (пароль в `/root/n8n_pub.cred` на сервере).
2. Credentials (одноразовый файл, удалить после):
   `docker cp creds.json n8n:/tmp/ && docker exec n8n n8n import:credentials --input=/tmp/creds.json`
   — в файле у каждого credential обязателен `"id"` (uuid), иначе
   «null value in column "id"». id — из `credentials_entity` (psql -d n8n).
3. `import:workflow` обоих JSON (с подставленными id credential и uuid-id
   workflow), затем `n8n update:workflow --id=<ID> --active=true` для обоих
   и **docker restart n8n** (без рестарта webhook не регистрируется).

## Обновление workflow

```bash
python tools/gen_n8n_pub.py          # правки в генераторе, не в JSON
# на сервере: подставить __CRED_*__, затем
python3 tools/update_wf.py /tmp/f_core.json /tmp/f_hook.json
docker restart n8n
```

Удаление/правка строк `workflow_entity` напрямую (кроме update_wf) — нельзя:
FK `versionId → workflow_history`, а исполняемая версия — `activeVersionId`.

## Проверка (dry-run)

```bash
TOKEN=$(grep ^PUB_ENGINE_TOKEN= /opt/agropilot-web/.env | cut -d= -f2)
PID=$(sudo -u postgres psql -d agropilot -Atc "INSERT INTO pub_posts (body_md) VALUES (\$\$test\$\$) RETURNING id;" | head -1)
curl -s -X POST https://mdked.hlab.kz/n8n/webhook/pub-publish \
  -H "X-PUB-TOKEN: $TOKEN" -H 'Content-Type: application/json' -d "{\"post_id\": $PID}"
# ожидание: {"ok":true,"data":{"post_id":"<PID>","skipped":true,"reason":"no active pending channels"}}
# и pub_posts.status='failed'
```

Живая публикация — после INSERT канала с токенами (§46.5).

## Грабли n8n 2.20 (зафиксировано при вводе Ф1)

- Execute Workflow → sub-workflow с Execute Workflow Trigger падает
  `WorkflowHasIssuesError`; решение — у sub-workflow свой webhook-триггер.
- Postgres-узел при пустом результате отдаёт 0 items — цепочка рвётся;
  селекты каналов агрегировать (`jsonb_agg`).
- `JSON.stringify` в `{{}}`-выражениях SQL подставляется без кавычек —
  литералы готовить в Code-узле.
- HTTP-код Respond to Webhook — только через `options.responseCode`.
- HTTP Request + Header Auth credential: нужны `authentication:
  "genericCredentialType"` и `genericAuthType: "httpHeaderAuth"`.
- Webhook-узел отдаёт тело запроса в `$json.body`.
