#!/usr/bin/env python3
# backend/questions/expire_job.py -- §40.1: TTL-джоба (systemd timer)
#
# Запуск на сервере: venv/bin/python -m backend.questions.expire_job
# (agropilot-questions-expire.timer, ежечасно Europe/Moscow).
# Логин сервисной учётки u7 из окружения (U7_PASSWORD в .env).

import asyncio
import json
import os
import sys
import urllib.request

BASE = os.environ.get("AGROPILOT_BASE", "http://127.0.0.1:5560/agropilot/api")


async def main() -> int:
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
        f"{BASE}/v1/petrushka/questions/expire",
        data=b"{}", method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read().decode())
    print(f"agent_questions expire: {resp['data']['expired']} шт.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
