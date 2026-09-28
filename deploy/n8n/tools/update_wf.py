#!/usr/bin/env python3
# Обновление §46-workflow в БД n8n: nodes/connections + новая версия в history.
# Использование: update_wf.py <core.json> <hook.json>
import json, sys, subprocess, uuid

def psql(q, payload=None):
    r = subprocess.run(['sudo', '-u', 'postgres', 'psql', '-d', 'n8n', '-Atc', q],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    return r.stdout.strip()

def update(name, path):
    d = json.load(open(path, encoding='utf-8'))
    nodes = json.dumps(d['nodes'], ensure_ascii=False)
    conns = json.dumps(d['connections'], ensure_ascii=False)
    wid = psql(f"SELECT id FROM workflow_entity WHERE name='{name}'")
    if not wid:
        print(f'{name}: не найден, пропуск'); return
    # authors — строка (например 'import'), берём из последней версии истории
    authors = psql(f'SELECT coalesce(authors, \'import\') FROM workflow_history '
                   f'WHERE "workflowId"=\'{wid}\' ORDER BY "createdAt" DESC LIMIT 1') or 'import'
    newvid = str(uuid.uuid4())
    psql(f'INSERT INTO workflow_history ("versionId","workflowId","authors","nodes","connections",'
         f'"name","autosaved","description") '
         f'SELECT \'{newvid}\', \'{wid}\', \'{authors}\', '
         f'\'{nodes.replace(chr(39), chr(39)*2)}\'::json, '
         f'\'{conns.replace(chr(39), chr(39)*2)}\'::json, '
         f'\'{name}\', false, \'\'')
    psql(f'UPDATE workflow_entity SET nodes=\'{nodes.replace(chr(39), chr(39)*2)}\'::json, '
         f'connections=\'{conns.replace(chr(39), chr(39)*2)}\'::json, '
         f'active=true, "versionId"=\'{newvid}\', "activeVersionId"=\'{newvid}\' WHERE id=\'{wid}\'')
    # старые версии истории оставляем (FK от entity), ревизии копятся безвредно
    print(f'{name}: обновлён, versionId={newvid[:8]}')

update('AgroPILOT PUB — publish-core (§46)', sys.argv[1])
update('AgroPILOT PUB — publish webhook (§46)', sys.argv[2])
