#!/usr/bin/env python3
# backend/myday/send_digest.py -- A6: утренняя сводка по расписанию (systemd timer)
#
# Запуск на сервере: venv/bin/python -m backend.myday.send_digest
# Логин сервисной учётки u7 из окружения (U7_PASSWORD в .env).

import asyncio
import os
import sys
import urllib.request
import json

BASE = os.environ.get("AGROPILOT_BASE", "http://127.0.0.1:5560/agropilot/api")


async def main() -> int:
    import urllib.parse

    password = os.environ.get("U7_PASSWORD", "")
    if not password:
        print("U7_PASSWORD не задан")
        return 2

    data = json.dumps({"login": "u7", "password": password}).encode()
    req = urllib.request.Request(
        f"{BASE}/v1/auth/login", data=data,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        tok = json.loads(r.read().decode())["data"]["access_token"]

    req = urllib.request.Request(
        f"{BASE}/v1/myday/digest",
        data=json.dumps({"send": True}).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read().decode())
    d = resp["data"]
    print(f"Сводка: telegram_sent={d.get('telegram_sent')} "
          f"overdue={len(d['tasks']['overdue'])} today={len(d['tasks']['today'])} "
          f"hot={len(d['deals_hot'])} inbound={len(d['inbounds_new'])} "
          f"posts={len(d['posts_in_review'])}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
