"""第六幕 API 面只读复测：软删模板 + 关联任务场景下两个模板端点的行为。

只发 GET（外加一个必然失败的登录 401，失败请求不触发审计中间件写入）。
"""
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE = "http://127.0.0.1:8010"
HERE = Path(__file__).resolve().parent
TEMPLATE_ID = "c742a65e-1828-4ae3-a8ca-833928a1043c"  # ISO 9001，已软删

# expert 是 TASK-20260326-799799 的负责人（has_related_task 路径）
sys.path.insert(0, str(HERE.parent))
from app.utils.security import create_access_token  # noqa: E402

TOKENS = {
    "expert(负责人)": create_access_token({"sub": "expert", "rv": None, "sid": "act6-probe"}),
    "admin(管理员)": create_access_token({"sub": "admin", "rv": None, "sid": "act6-probe"}),
}


def get(path: str, token: str):
    req = urllib.request.Request(BASE + path, headers={"Authorization": f"Bearer {token}"})
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
        return resp.status, (time.perf_counter() - t) * 1000, body
    except urllib.error.HTTPError as e:
        return e.code, (time.perf_counter() - t) * 1000, None


def count_leaves(nodes) -> int:
    n = 0
    for node in nodes or []:
        if node.get("children"):
            n += count_leaves(node["children"])
        else:
            n += 1
    return n


def main() -> None:
    for label, token in TOKENS.items():
        for path in (f"/api/templates/{TEMPLATE_ID}", f"/api/templates/{TEMPLATE_ID}/items"):
            status, ms, body = get(path, token)
            if body and isinstance(body.get("data"), dict):
                items = body["data"].get("items")
                if isinstance(items, list):
                    detail = f"items={len(items)} 顶层节点, 叶子={count_leaves(items)}"
                else:
                    detail = f"keys={list(body['data'].keys())[:6]}"
            else:
                detail = ""
            print(f"{label:16s} {status}  {ms:6.0f}ms  {path.split('/api')[1]}  {detail}")

    # 软删账号登录：期望 401（而非 Q-02 时代的 500）
    req = urllib.request.Request(
        BASE + "/api/auth/login",
        data=json.dumps({"username": "admin_deleted_1789896854", "password": "admin123"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            print(f"软删账号登录: {resp.status}（异常！不应成功）")
    except urllib.error.HTTPError as e:
        print(f"软删账号登录: HTTP {e.code}（期望 401/400，不再是 500）")


if __name__ == "__main__":
    sys.exit(main())
