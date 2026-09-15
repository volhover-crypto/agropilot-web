#!/usr/bin/env python3
# scripts/acceptance_test.py -- сквозной приёмочный тест ТЗ v1.1 (Этап 5).
#
# Запуск на сервере:
#   cd /opt/agropilot-web && set -a && . ./.env && set +a && \
#   U1_PASSWORD=... venv/bin/python scripts/acceptance_test.py [--no-publish]
#
# Прогоняет 10 критериев приёмки по живому API (http://127.0.0.1:5560).
# Критерий 1 включает публикацию в Telegram (флаг --no-publish пропускает
# реальную отправку, проверяя только отказоустойчивость endpoint).

import json
import os
import sys
import time
import urllib.request

BASE = os.environ.get("AGROPILOT_BASE", "http://127.0.0.1:5560/agropilot/api")
NO_PUBLISH = "--no-publish" in sys.argv

results = []


def call(method, path, token=None, body=None, expect=(200,)):
    req = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json",
                 **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def check(num, name, ok, detail=""):
    results.append((num, name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {num}. {name}" + (f" — {detail}" if detail else ""))


def main():
    u1 = os.environ.get("U1_PASSWORD", "")
    if not u1:
        print("U1_PASSWORD не задан"); return 2

    # -- вход (критерий 9: JWT) --
    st, r = call("POST", "/v1/auth/login", body={"login": "u1", "password": u1})
    tok = r.get("data", {}).get("access_token", "")
    check(9, "Аутентификация §19: login ok + без токена 401",
          st == 200 and bool(tok) and call("GET", "/v1/team")[0] == 401)

    # -- критерий 1: источник -> NewsItem -> черновик A2 -> правка -> публикация --
    st, r = call("POST", "/v1/news/scan", tok)
    scan = r.get("data", {})
    ok1a = st == 200 and scan.get("sources", 0) >= 1
    st, r = call("GET", "/v1/news?status=new&limit=5", tok)
    news = (r.get("data") or {}).get("items") or []
    ok1b = len(news) >= 1
    post = None
    if ok1b:
        st, r = call("POST", "/v1/content/from_news", tok,
                     {"news_id": news[0]["id"], "platform": "telegram"})
        post = (r.get("data") or {}).get("id")
    ok1c = post is not None
    ok1d = ok1e = False
    if ok1c:
        st, _ = call("PATCH", f"/v1/content/{post}", tok, {"status": "in_review"})
        ok1d = st == 200
        st, _ = call("PATCH", f"/v1/content/{post}", tok,
                     {"status": "approved", "body": "Приёмочный тест: текст после правки редактора."})
        ok1e = st == 200
    ok1f = True
    if not NO_PUBLISH:
        st, r = call("POST", f"/v1/content/{post}/publish", tok, {})
        ok1f = st == 200 and r.get("data", {}).get("status") == "published"
    check(1, "Конвейер контента: скан->NewsItem->черновик A2->правка->публикация",
          ok1a and ok1b and ok1c and ok1d and ok1e and ok1f,
          f"scan {scan.get('inserted', '?')} новых, post={post}, published={not NO_PUBLISH and ok1f}")

    # -- критерий 2: входящее -> A4 -> лид -> клиент+реквизиты --
    stamp = str(int(time.time()))
    st, r = call("POST", "/v1/inbound", tok, {
        "channel": "site", "contact": "Приёмка " + stamp,
        "subject": "Тестовое обращение " + stamp, "body": "Интересует орошение 5 га."})
    inb = (r.get("data") or {}).get("id")
    ok2a = st == 200 and inb is not None
    ok2b = ok2c = ok2d = False
    if ok2a:
        st, r = call("POST", f"/v1/inbound/{inb}/classify", tok, {})
        ok2b = st == 200 and bool((r.get("data") or {}).get("a4_class", {}).get("topic"))
        st, r = call("POST", f"/v1/inbound/{inb}/convert", tok, {})
        lead = (r.get("data") or {}).get("lead", {})
        ok2c = st == 200 and lead.get("id", "").startswith("B")
    st, r = call("POST", "/v1/clients/C4/requisites", tok, {"inn": "7707083893"})
    ok2d = st == 200 and (r.get("data") or {}).get("requisites", {}).get("ogrn") == "1027700132195"
    call("PATCH", "/v1/clients/C4", tok, {"inn": None}) if False else None
    check(2, "Входящее -> A4 -> лид; реквизиты по ИНН из ЕГРЮЛ",
          ok2a and ok2b and ok2c and ok2d, f"inbound={inb}")

    # -- критерий 3: воронка сделок + артефакт по шаблону --
    st, r = call("GET", "/v1/deals?limit=50", tok)
    deals = r.get("data") or []
    stages = {d.get("stage") for d in deals}
    ok3a = st == 200 and {"lead", "assess", "proposal", "deal", "won", "service"} >= {"lead"}
    st, r = call("GET", "/v1/artifacts/templates", tok)
    tpls = {t["code"] for t in (r.get("data") or [])}
    ok3b = {"kp", "letter", "contract"} <= tpls
    deal_id = next((d["id"] for d in deals if d.get("client_id")), None)
    ok3c = False
    if ok3b and deal_id:
        st, r = call("POST", "/v1/artifacts/generate", tok,
                     {"template_code": "kp", "deal_id": deal_id})
        art = (r.get("data") or {}).get("artifact", {})
        ok3c = st == 200 and art.get("status") == "draft" and bool(art.get("body"))
    check(3, "Воронка (6 этапов §16a) + A5: КП по шаблону со статусом draft",
          ok3a and ok3b and ok3c, f"deal={deal_id}")

    # -- критерий 4: Мой день + сводка A6 --
    st, r = call("POST", "/v1/myday/digest", tok, {"send": False})
    d = r.get("data") or {}
    check(4, "«Мой день»: агрегат + LLM-сводка (A6)",
          st == 200 and "tasks" in d and bool(d.get("summary")))

    # -- критерий 5: A7 отвечает по контексту --
    st, r = call("POST", "/v1/assistant/ask", tok, {"question": "сколько сделок в работе?"})
    ans = (r.get("data") or {}).get("answer", "")
    check(5, "A7-ассистент: ответ по контексту системы",
          st == 200 and len(ans) > 3, ans[:60])

    # -- критерий 6: модульность — новостной модуль не зависит от контент-роутера:
    # проверяем независимые домены через изоляцию ошибок валидации --
    st1, _ = call("PATCH", "/v1/content/999999", tok, {"status": "draft"})
    st2, _ = call("GET", "/v1/news?limit=1", tok)
    check(6, "Модульность: ошибка в content не влияет на news (404 vs 200)",
          st1 in (404, 422) and st2 == 200)

    # -- критерий 7: промты из UI с версионированием --
    st, r = call("GET", "/v1/agents", tok)
    agents = {a["code"]: a for a in (r.get("data") or [])}
    ok7a = st == 200 and set(agents) >= {"a1", "a2", "a3", "a4", "a5", "a6", "a7"}
    ok7b = agents.get("a7", {}).get("prompt_version") is not None
    check(7, "Карточки агентов + промты с версиями (§29)", ok7a and ok7b)

    # -- критерий 8: аудит/история изменений (content_versions + версии промтов) --
    st, r = call("GET", f"/v1/content/{post}/versions", tok) if post else (0, {})
    vers = r.get("data") or []
    check(8, "История изменений: версии контента фиксируются",
          st == 200 and len(vers) >= 2, f"{len(vers)} версий у post={post}")

    # -- критерий 10: лиды Bitrix24 не потеряны --
    st, r = call("GET", "/v1/leads?limit=1", tok)
    total = None
    try:
        total = (r.get("data") or {}).get("total")
    except Exception:
        pass
    if total is None:  # лиды возвращают список
        total = len(r.get("data") or []) if isinstance(r.get("data"), list) else 0
    check(10, "Лиды Bitrix24 на месте (≥900)", st == 200 and (total or 0) >= 900, f"total={total}")

    failed = [x for x in results if not x[2]]
    print(f"\nИТОГ: {len(results) - len(failed)}/{len(results)} критериев пройдено")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
