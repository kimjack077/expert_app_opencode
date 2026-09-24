"""对本地新代码实例（8010）做只读 GET 计时探测。不执行任何写请求。"""
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8010"
HERE = Path(__file__).resolve().parent

if len(sys.argv) > 1:
    BASE = f"http://127.0.0.1:{sys.argv[1]}"

_username, token = (HERE / "probe_token.txt").read_text(encoding="utf-8").splitlines()

ENDPOINTS = [
    "/api/templates",
    "/api/templates",          # 第二次：命中鉴权缓存
    "/api/tasks",
    "/api/records",
    "/api/enterprises",
    "/api/audit-projects",
    "/api/users",
    "/api/statistics/overview",
    "/api/tasks?skip=20",      # 翻页：旧实现要 2 次往返，新实现 1 次
    "/api/records?skip=20",
]


def timed_get(path: str) -> tuple[float, int, object]:
    req = urllib.request.Request(
        BASE + path, headers={"Authorization": f"Bearer {token}"}
    )
    t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read()
    elapsed = (time.perf_counter() - t) * 1000
    payload = json.loads(body)
    return elapsed, resp.status, payload.get("data")


def total_of(data) -> object:
    if isinstance(data, dict):
        return data.get("total")
    if isinstance(data, list):
        return f"list[{len(data)}]"
    return type(data).__name__


def main() -> None:
    # 预热一次（连接池建连）
    try:
        timed_get("/api/health")
    except Exception as exc:
        print(f"warmup failed: {exc}")
    for path in ENDPOINTS:
        try:
            ms, status, data = timed_get(path)
            print(f"{ms:7.0f} ms  {status}  total={total_of(data)}  {path}")
        except Exception as exc:
            print(f"   ERROR  {path}: {exc}")


if __name__ == "__main__":
    sys.exit(main())
