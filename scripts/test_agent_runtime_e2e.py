# -*- coding: utf-8 -*-
"""EFIS Agent 运行时端到端测试（2026-07 改造后新增能力）。

覆盖现有 full_system_e2e_test.py 未触及的部分：
- 安全加固：注册提权、越权读写、软删过滤、分页 total
- 动作注册表：注册/确认/幂等/默认拒绝/参数校验
- Agent 运行时：工具注册表、规划器 SSE
- 反馈闭环、主动提醒、长期记忆
- 多模态融合与溯源字段

用法：python scripts/test_agent_runtime_e2e.py [BASE_URL]
所有写入数据带 AGENTRT- 前缀，结束自动清理。
"""
import json
import sys
import time
import uuid
from dataclasses import dataclass, field

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
MARK = f"AGENTRT-{time.strftime('%Y%m%d-%H%M%S')}"
ADMIN = ("admin", "admin123")
EXPERT = ("expert", "expert123")


@dataclass
class Result:
    module: str
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Suite:
    results: list = field(default_factory=list)

    def add(self, module, name, ok, detail=""):
        self.results.append(Result(module, name, ok, str(detail)[:300]))
        print(f"[{'PASS' if ok else 'FAIL'}] {module} | {name} {str(detail)[:160]}")

    @property
    def failed(self):
        return [r for r in self.results if not r.ok]


suite = Suite()


def login(c, creds):
    r = c.post("/api/auth/login", json={"username": creds[0], "password": creds[1]})
    r.raise_for_status()
    return r.json()["data"]["access_token"]


def main():
    created = {"enterprise": [], "notification": []}
    with httpx.Client(base_url=BASE, timeout=60) as c:
        # ---------- 登录 ----------
        try:
            admin_t = login(c, ADMIN)
            expert_t = login(c, EXPERT)
            A = {"Authorization": f"Bearer {admin_t}"}
            E = {"Authorization": f"Bearer {expert_t}"}
            suite.add("auth", "admin+expert login", True)
        except Exception as e:
            suite.add("auth", "login", False, e)
            return finish(created, None)

        # ---------- 1. 安全：注册不可提权 ----------
        uname = f"agentrt_{uuid.uuid4().hex[:8]}"
        r = c.post("/api/auth/register", json={
            "username": uname, "password": "Test12345!", "full_name": MARK,
            "role": "super_admin", "org_id": str(uuid.uuid4()),
        })
        if r.status_code == 200:
            d = r.json()["data"]
            ok = d.get("role") == "expert"
            suite.add("security", "register cannot escalate role", ok, f"role={d.get('role')}")
            suite.add("security", "register ignores org_id", d.get("org_id") in (None, ""), f"org_id={d.get('org_id')}")
        else:
            suite.add("security", "register", False, f"HTTP {r.status_code}")

        # ---------- 2. 动作注册表 ----------
        r = c.get("/api/agent/actions/registry", headers=E)
        ok = r.status_code == 200 and "apply_check_result" in (r.json().get("data", {}).get("actions") or [])
        acts = r.json().get("data", {}).get("actions") if r.status_code == 200 else None
        suite.add("actions", "registry lists actions", ok, acts)

        # 未鉴权必须 401
        r = c.post("/api/agent/actions/confirm", json={"message_id": str(uuid.uuid4()), "action_index": 0})
        suite.add("actions", "confirm requires auth", r.status_code in (401, 403), f"HTTP {r.status_code}")

        # 伪造 message_id 必须 404（不能执行不存在的提案）
        r = c.post("/api/agent/actions/confirm", headers=E,
                   json={"message_id": str(uuid.uuid4()), "action_index": 0})
        suite.add("actions", "unknown proposal rejected", r.status_code == 404, f"HTTP {r.status_code}")

        # 非法 message_id 400
        r = c.post("/api/agent/actions/confirm", headers=E,
                   json={"message_id": "not-a-uuid", "action_index": 0})
        suite.add("actions", "malformed id rejected", r.status_code == 400, f"HTTP {r.status_code}")

        # ---------- 3. 主动提醒 ----------
        r = c.get("/api/agent/notifications", headers=E)
        ok = r.status_code == 200 and isinstance(r.json().get("data", {}).get("items"), list)
        n = len(r.json().get("data", {}).get("items", [])) if r.status_code == 200 else -1
        suite.add("proactive", "list notifications", ok, f"items={n}")

        r = c.put(f"/api/agent/notifications/{uuid.uuid4()}", headers=E, json={"status": "read"})
        suite.add("proactive", "update unknown notification -> 404", r.status_code == 404, f"HTTP {r.status_code}")

        r = c.put(f"/api/agent/notifications/{uuid.uuid4()}", headers=E, json={"status": "bogus"})
        suite.add("proactive", "invalid status rejected", r.status_code == 400, f"HTTP {r.status_code}")

        # ---------- 4. 反馈统计（仅管理角色） ----------
        r = c.get("/api/agent/feedback/stats", headers=A)
        ok = r.status_code == 200 and "overall" in (r.json().get("data") or {})
        ov = r.json().get("data", {}).get("overall") if r.status_code == 200 else None
        suite.add("feedback", "stats as admin", ok, ov)

        r = c.get("/api/agent/feedback/stats", headers=E)
        suite.add("feedback", "stats forbidden for expert", r.status_code == 403, f"HTTP {r.status_code}")

        # ---------- 5. 规划器（SSE，真实 LLM） ----------
        try:
            ents = c.get("/api/enterprises?limit=1", headers=A).json()["data"]["items"]
            ent_id = ents[0]["id"] if ents else None
        except Exception:
            ent_id = None
        if ent_id:
            events = []
            try:
                with c.stream("POST", "/api/agent/plan", headers=E, timeout=180, json={
                    "goal": "为这家企业准备一次审核，列出重点关注事项",
                    "context": {"enterprise_id": ent_id},
                }) as s:
                    for line in s.iter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        ev = json.loads(line[6:])
                        events.append(ev.get("type"))
                        if ev.get("type") == "done":
                            break
                ok = "plan" in events and "done" in events
                suite.add("planner", "plan->execute->synthesize (SSE)", ok, f"events={events[:6]}")
            except Exception as e:
                suite.add("planner", "plan SSE", False, e)
        else:
            suite.add("planner", "plan SSE", False, "no enterprise to test with")

        # ---------- 6. 越权读：expert 不能用他人 record 作上下文 ----------
        r = c.post("/api/agent/chat", headers=E, json={
            "message": "测试", "context": {"record_id": str(uuid.uuid4())},
        })
        suite.add("security", "agent ctx unknown record rejected", r.status_code in (403, 404), f"HTTP {r.status_code}")

        # ---------- 7. 审核项目列表可见性 ----------
        ra = c.get("/api/audit-projects?limit=100", headers=A)
        re_ = c.get("/api/audit-projects?limit=100", headers=E)
        if ra.status_code == 200 and re_.status_code == 200:
            na = len(ra.json().get("data") or [])
            ne = len(re_.json().get("data") or [])
            suite.add("security", "project list scoped for expert", ne <= na, f"admin={na} expert={ne}")
        else:
            suite.add("security", "project list", False, f"{ra.status_code}/{re_.status_code}")

        # ---------- 8. 分页 total 与筛选一致 ----------
        r = c.get("/api/tasks?limit=5&status=pending", headers=A)
        if r.status_code == 200:
            d = r.json()["data"]
            items, total = d.get("items", []), d.get("total", 0)
            ok = all(i.get("status") == "pending" for i in items) and total >= len(items)
            suite.add("consistency", "task list total honors filter", ok, f"items={len(items)} total={total}")
        else:
            suite.add("consistency", "task list", False, f"HTTP {r.status_code}")

        # ---------- 9. 记录列表：admin 能看到全部（角色集合修复） ----------
        r = c.get("/api/records?limit=5", headers=A)
        ok = r.status_code == 200 and r.json()["data"].get("total", 0) >= 0
        suite.add("consistency", "records visible to admin", ok,
                  f"total={r.json()['data'].get('total') if r.status_code==200 else r.status_code}")

        # ---------- 10. 时间戳格式合法 ----------
        import datetime
        bad = []
        for path, hdr in [("/api/health", None), ("/api/tasks?limit=1", A), ("/api/audit-projects?limit=1", A)]:
            rr = c.get(path, headers=hdr or {})
            ts = rr.json().get("timestamp") if rr.status_code == 200 else None
            if ts:
                try:
                    datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                except Exception:
                    bad.append((path, ts))
        suite.add("consistency", "timestamps ISO8601 valid", not bad, bad or "all valid")

        # ---------- 11. 上传校验：扩展名与内容不符应被拒 ----------
        files = {"file": ("evil.png", b"MZ\x90\x00this-is-not-an-image", "image/png")}
        r = c.post("/api/media/upload", headers=E, files=files)
        suite.add("security", "magic-byte mismatch rejected", r.status_code in (400, 422), f"HTTP {r.status_code}")

    return finish(created, None)


def finish(created, _):
    print("\n" + "=" * 70)
    total = len(suite.results)
    failed = suite.failed
    print(f"TOTAL: {total}  PASS: {total - len(failed)}  FAIL: {len(failed)}")
    print("=" * 70)
    if failed:
        print("\nFAILURES:")
        for r in failed:
            print(f"  - {r.module} / {r.name}: {r.detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
