"""Verify H5 task execution API path (record vs task)."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import text

from app.database import AsyncSessionLocal

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")
TASK_ID = "58c7d713-a3ee-40ab-b6b8-1a6ef59fdf63"
TASK_WITH_TPL = "8e9bd0fb-cb13-419e-8a52-48e348e263f9"


async def login(client: httpx.AsyncClient, username: str, password: str) -> str:
    r = await client.post(
        f"{BASE}/api/auth/login",
        json={"username": username, "password": password},
    )
    r.raise_for_status()
    data = r.json()
    token = data.get("data", {}).get("access_token") or data.get("access_token")
    if not token:
        raise RuntimeError(f"login failed for {username}: {data}")
    return token


async def main():
    # Prefer known test accounts
    candidates = [
        ("test_auditor", "123456"),
        ("test_auditor", "password"),
        ("admin", "admin123"),
        ("admin", "123456"),
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        token = None
        user = None
        for username, password in candidates:
            try:
                token = await login(client, username, password)
                user = username
                print(f"logged in as {username}")
                break
            except Exception as e:
                print(f"login {username} failed: {e}")

        if not token:
            print("No login worked, skip remote API checks")
            return

        headers = {"Authorization": f"Bearer {token}"}

        for label, tid in [("no_template", TASK_ID), ("with_template", TASK_WITH_TPL)]:
            print(f"\n=== {label} {tid} ===")
            r = await client.get(f"{BASE}/api/tasks/{tid}", headers=headers)
            print("GET task", r.status_code, r.json().get("code"), r.json().get("message"))
            body = r.json().get("data") or {}
            print("  template_id:", body.get("template_id"), "status:", body.get("status"))

            r2 = await client.get(f"{BASE}/api/tasks/{tid}/records", headers=headers)
            print("GET task records", r2.status_code, r2.json().get("code"))
            recs = r2.json().get("data") or []
            print("  records count:", len(recs))
            if recs:
                print("  first keys:", list(recs[0].keys()))
                print("  first template_item_id:", recs[0].get("template_item_id"))

            # simulate old broken path
            r3 = await client.get(f"{BASE}/api/records/{tid}", headers=headers)
            print("GET record by task id (should 404)", r3.status_code)

            tpl = body.get("template_id")
            if tpl:
                r4 = await client.get(f"{BASE}/api/templates/{tpl}", headers=headers)
                print("GET template", r4.status_code, r4.json().get("code"))
                items = (r4.json().get("data") or {}).get("items") or []
                print("  template items roots:", len(items))


if __name__ == "__main__":
    asyncio.run(main())
