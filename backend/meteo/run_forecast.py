#!/usr/bin/env python3
# backend/meteo/run_forecast.py -- §34: MIA по расписанию (systemd timers)
#
# Запуск на сервере (сервисный вход u7 из окружения, U7_PASSWORD в .env):
#   venv/bin/python -m backend.meteo.run_forecast --horizon 24|72|120
# Прогоняет все активные подписки с этим горизонтом, send=true (Telegram).

import argparse
import asyncio
import json
import os
import sys
import urllib.request

BASE = os.environ.get("AGROPILOT_BASE", "http://127.0.0.1:5560/agropilot/api")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, required=True, choices=(24, 72, 120))
    args = ap.parse_args()

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

    req = urllib.request.Request(f"{BASE}/v1/meteo/subs",
                                 headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        subs = json.loads(r.read().decode())["data"]

    todo = [s for s in subs if s["active"] and args.horizon in s["horizons"]]
    if not todo:
        print(f"подписок с горизонтом {args.horizon} нет")
        return 0
    done, failed = 0, 0
    for s in todo:
        body = json.dumps({"point_id": s["point_id"], "crop_code": s["crop_code"],
                           "horizon_h": args.horizon, "send": True}).encode()
        req = urllib.request.Request(
            f"{BASE}/v1/meteo/run", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {tok}"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read().decode())["data"]
            print(f"{s['point_id']}/{s['crop_code']}/{args.horizon}ч: "
                  f"critical={d['critical']} tg={d['telegram_sent']}")
            done += 1
        except Exception as e:
            print(f"{s['point_id']}/{s['crop_code']}: ОШИБКА {str(e)[:160]}")
            failed += 1
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
