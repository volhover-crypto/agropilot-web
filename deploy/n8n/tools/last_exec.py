#!/usr/bin/env python3
# Разбор исполнения n8n (compact-формат с индексными ссылками): последний узел,
# ошибка, статусы всех узлов. Использование: last_exec.py [execution_id]
import json, subprocess, sys

eid = sys.argv[1] if len(sys.argv) > 1 else None
def psql(q):
    return subprocess.run(['sudo','-u','postgres','psql','-d','n8n','-Atc',q],
                          capture_output=True, text=True).stdout.strip()

if not eid:
    eid = psql('SELECT id FROM execution_entity ORDER BY id DESC LIMIT 1')
print('execution', eid)
raw = psql(f'SELECT data::text FROM execution_data WHERE "executionId"={eid}')
arr = json.loads(raw)

def deref(o, depth=0):
    if depth > 12: return '<deep>'
    if isinstance(o, str) and o.isdigit() and int(o) < len(arr):
        return deref(arr[int(o)], depth+1)
    if isinstance(o, dict):
        return {k: deref(v, depth+1) for k, v in o.items()}
    if isinstance(o, list):
        return [deref(v, depth+1) for v in o]
    return o

d = deref(arr[0])
res = d.get('resultData', {})
err = res.get('error', {})
if err:
    print('ERROR:', err.get('name'), '|', str(err.get('message'))[:300])
run = res.get('runData', {}) or {}
for name, runs in run.items():
    if isinstance(runs, list) and runs and isinstance(runs[-1], dict):
        last = runs[-1]
        msg = ''
        e = last.get('error')
        if e: msg = str(e.get('message', ''))[:200]
        print(f'- {name}: {last.get("status")}{(" | " + msg) if msg else ""}')
print('lastNodeExecuted:', res.get('lastNodeExecuted'))

# детальный вывод первого json каждого узла
print('=== data of nodes ===')
for name, runs in run.items():
    if isinstance(runs, list) and runs and isinstance(runs[-1], dict):
        main = runs[-1].get('data') or {}
        mlist = main.get('main') or []
        j = None
        if mlist and isinstance(mlist[0], list) and mlist[0] and isinstance(mlist[0][0], dict):
            j = mlist[0][0].get('json')
        print(f'- {name}:', json.dumps(j, ensure_ascii=False, default=str)[:200] if j else 'NO OUTPUT')
