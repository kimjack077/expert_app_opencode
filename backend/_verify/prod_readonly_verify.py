"""线上只读验证：健康检查 + 关键列表接口（本地签名 token，不写库、不登录）。"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.utils.security import create_access_token  # noqa: E402

BASE = "http://49.232.213.79:8000"
TOKEN = create_access_token({"sub": "admin", "rv": None, "sid": "post-deploy-verify"})


def call(path: str, expect_json: bool = True):
    req = urllib.request.Request(BASE + path, headers={"Authorization": f"Bearer {TOKEN}"})
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read()
        status = e.code
    ms = (time.perf_counter() - t) * 1000
    try:
        body = json.loads(raw)
    except Exception:
        body = None
    return status, ms, body


def describe(body):
    if not isinstance(body, dict):
        return ""
    data = body.get("data")
    if isinstance(data, dict) and "total" in data:
        return f"total={data['total']}, items={len(data.get('items') or [])}"
    if isinstance(data, list):
        return f"list[{len(data)}]"
    if isinstance(data, dict):
        return f"keys={list(data.keys())[:5]}"
    return ""


print("--- 线上健康检查 ---")
try:
    with urllib.request.urlopen(BASE + "/api/health", timeout=20) as r:
        print(f"health: {r.status} {r.read().decode()[:80]}")
except Exception as exc:
    print(f"health ERROR: {exc}")

print("\n--- 关键接口（含分页 total 正确性）---")
for path in (
    "/api/auth/me",
    "/api/templates",
    "/api/tasks",
    "/api/tasks?skip=20",
    "/api/records",
    "/api/records?skip=20",
    "/api/enterprises",
    "/api/audit-projects",
    "/api/users",
    "/api/statistics/overview",
):
    status, ms, body = call(path)
    print(f"{status}  {ms:6.0f}ms  {path:28s} {describe(body)}  msg={body.get('message') if isinstance(body, dict) else None}")
