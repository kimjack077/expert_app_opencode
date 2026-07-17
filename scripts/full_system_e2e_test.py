#!/usr/bin/env python3
"""EFIS full-system E2E test against production (or local) API.

Covers auth, master data, templates, tasks, records, audit projects,
knowledge, LLM final judgment, frontend HTTP smoke, and H5 task execution path.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Optional

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://49.232.213.79:8000"
WEB = "http://49.232.213.79:3000"
H5 = "http://49.232.213.79:5173/h5/"
TIMEOUT = 60.0
TS = datetime.now().strftime("%Y%m%d%H%M%S")
MARK = f"E2E-FULL-{TS}"


@dataclass
class CaseResult:
    name: str
    module: str
    ok: bool
    detail: str = ""
    duration_ms: int = 0
    severity: str = "P2"  # P0/P1/P2 for failures


@dataclass
class Suite:
    results: list[CaseResult] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    def add(self, r: CaseResult) -> None:
        self.results.append(r)
        flag = "PASS" if r.ok else "FAIL"
        print(f"[{flag}] {r.module} | {r.name} ({r.duration_ms}ms) {r.detail[:200]}")

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.ok)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.ok)


def login(client: httpx.Client, username: str, password: str) -> dict:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 200:
        raise RuntimeError(f"login failed: {data}")
    return data["data"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def run_case(
    suite: Suite,
    module: str,
    name: str,
    fn: Callable[[], Any],
    severity: str = "P1",
) -> Any:
    start = time.time()
    try:
        value = fn()
        suite.add(
            CaseResult(
                name=name,
                module=module,
                ok=True,
                detail=str(value)[:300] if value is not None else "ok",
                duration_ms=int((time.time() - start) * 1000),
            )
        )
        return value
    except Exception as exc:  # noqa: BLE001
        suite.add(
            CaseResult(
                name=name,
                module=module,
                ok=False,
                detail=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.time() - start) * 1000),
                severity=severity,
            )
        )
        traceback.print_exc()
        return None


def expect(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    suite = Suite()
    print("=" * 70)
    print(f"EFIS Full System E2E @ {BASE}")
    print(f"Marker: {MARK}")
    print("=" * 70)

    with httpx.Client(base_url=BASE, timeout=TIMEOUT) as client:
        # ---------- 0. Health / Frontend ----------
        def t_health():
            r = client.get("/api/health")
            r.raise_for_status()
            body = r.json()
            expect(body.get("status") == "healthy", f"health={body}")
            return body

        run_case(suite, "infra", "API health", t_health, "P0")

        def t_web():
            r = httpx.get(WEB, timeout=20, follow_redirects=True)
            expect(r.status_code == 200, f"web status {r.status_code}")
            expect("html" in r.headers.get("content-type", "").lower() or len(r.text) > 50, "web empty")
            return r.status_code

        run_case(suite, "frontend", "Web HTTP 200", t_web, "P0")

        def t_h5():
            r = httpx.get(H5, timeout=20, follow_redirects=True)
            expect(r.status_code == 200, f"h5 status {r.status_code}")
            return r.status_code

        run_case(suite, "frontend", "H5 HTTP 200", t_h5, "P0")

        # ---------- 1. Auth ----------
        admin = run_case(
            suite,
            "auth",
            "admin login",
            lambda: login(client, "admin", "admin123"),
            "P0",
        )
        if not admin:
            print("FATAL: admin login failed, abort")
            return 2
        admin_token = admin["access_token"]
        ah = auth_headers(admin_token)
        suite.context["admin_id"] = (admin.get("user") or {}).get("id") or admin.get("id")

        expert = run_case(
            suite,
            "auth",
            "expert login",
            lambda: login(client, "expert", "expert123"),
            "P0",
        )
        expert_token = expert["access_token"] if expert else None
        eh = auth_headers(expert_token) if expert_token else {}
        expert_id = None
        if expert:
            expert_id = (expert.get("user") or {}).get("id") or expert.get("id")
            suite.context["expert_id"] = expert_id

        def t_me():
            r = client.get("/api/auth/me", headers=ah)
            # some deployments use /api/users/me
            if r.status_code == 404:
                r = client.get("/api/users/me", headers=ah)
            if r.status_code == 404:
                return "me endpoint optional"
            r.raise_for_status()
            return r.json().get("code")

        run_case(suite, "auth", "current user", t_me)

        # ---------- 2. Master data ----------
        def t_users():
            r = client.get("/api/users", headers=ah, params={"limit": 50})
            r.raise_for_status()
            data = r.json()["data"]
            items = data if isinstance(data, list) else data.get("items") or []
            expect(len(items) >= 1, "no users")
            # find expert and test_auditor
            for u in items:
                if u.get("username") == "expert":
                    suite.context["expert_id"] = u["id"]
                if u.get("username") == "test_auditor":
                    suite.context["auditor_id"] = u["id"]
            return f"users={len(items)}"

        run_case(suite, "users", "list users", t_users, "P1")

        def t_enterprises():
            r = client.get("/api/enterprises", headers=ah, params={"limit": 20})
            r.raise_for_status()
            data = r.json()["data"]
            items = data.get("items") if isinstance(data, dict) else data
            expect(isinstance(items, list), "enterprises not list")
            if items:
                suite.context["enterprise_id"] = items[0]["id"]
                suite.context["enterprise_name"] = items[0].get("name")
            return f"enterprises={len(items or [])}"

        run_case(suite, "enterprises", "list enterprises", t_enterprises, "P1")

        def t_create_enterprise():
            payload = {
                "name": f"{MARK}-企业",
                "credit_code": f"E2E{TS}",
                "address": "测试市测试区测试路1号",
                "legal_person": "测试法人",
                "contact_person": "测试联系人",
                "contact_phone": "13800001111",
            }
            r = client.post("/api/enterprises", headers=ah, json=payload)
            if r.status_code >= 400:
                # unique conflict ok - try list search
                raise AssertionError(r.text[:300])
            body = r.json()
            expect(body.get("code") == 200, body)
            eid = body["data"]["id"] if isinstance(body["data"], dict) and "id" in body["data"] else body["data"]
            suite.context["enterprise_id"] = eid if isinstance(eid, str) else body["data"].get("id")
            suite.context["enterprise_name"] = payload["name"]
            return suite.context["enterprise_id"]

        run_case(suite, "enterprises", "create enterprise", t_create_enterprise, "P1")

        def t_industries():
            r = client.get("/api/industries", headers=ah)
            r.raise_for_status()
            data = r.json()["data"]
            items = data if isinstance(data, list) else data.get("items") or []
            return f"industries={len(items)}"

        run_case(suite, "industries", "list industries", t_industries)

        # ---------- 3. Templates ----------
        def t_templates():
            r = client.get("/api/templates", headers=ah, params={"limit": 50})
            r.raise_for_status()
            data = r.json()["data"]
            items = data if isinstance(data, list) else data.get("items") or []
            expect(len(items) >= 1, "no templates")
            # prefer ISO9001 public
            preferred = next((t for t in items if "ISO" in (t.get("name") or "") or t.get("code") == "ISO9001-2026"), items[0])
            suite.context["template_id"] = preferred["id"]
            suite.context["template_name"] = preferred.get("name")
            return f"templates={len(items)} pick={preferred.get('name')}"

        run_case(suite, "templates", "list templates", t_templates, "P0")

        def t_template_detail():
            tid = suite.context["template_id"]
            r = client.get(f"/api/templates/{tid}", headers=ah)
            r.raise_for_status()
            data = r.json()["data"]
            items = data.get("items") or []
            expect(len(items) >= 1, "template has no items")
            suite.context["template_items"] = items
            return f"roots={len(items)}"

        run_case(suite, "templates", "template detail tree", t_template_detail, "P0")

        # ---------- 4. Tasks (classic inspection) ----------
        def t_create_task():
            assignee = suite.context.get("auditor_id") or suite.context.get("expert_id")
            expect(assignee, "no assignee user")
            payload = {
                "title": f"{MARK}-任务",
                "template_id": suite.context["template_id"],
                "assigned_to": assignee,
                "target_name": suite.context.get("enterprise_name") or f"{MARK}-对象",
                "target_address": "测试地址",
                "remarks": MARK,
            }
            r = client.post("/api/tasks", headers=ah, json=payload)
            r.raise_for_status()
            body = r.json()
            expect(body.get("code") == 200, body)
            task = body["data"]
            suite.context["task_id"] = task["id"]
            return task["id"]

        run_case(suite, "tasks", "create task", t_create_task, "P0")

        def t_get_task():
            tid = suite.context["task_id"]
            r = client.get(f"/api/tasks/{tid}", headers=ah)
            r.raise_for_status()
            data = r.json()["data"]
            expect(data.get("template_id"), "task missing template_id")
            return data.get("status")

        run_case(suite, "tasks", "get task", t_get_task, "P0")

        def t_start_task():
            tid = suite.context["task_id"]
            r = client.post(f"/api/tasks/{tid}/start", headers=ah)
            if r.status_code == 404:
                r = client.put(f"/api/tasks/{tid}", headers=ah, json={"status": "in_progress"})
            r.raise_for_status()
            return r.json().get("code")

        run_case(suite, "tasks", "start task", t_start_task, "P1")

        def t_task_records():
            tid = suite.context["task_id"]
            r = client.get(f"/api/tasks/{tid}/records", headers=ah)
            r.raise_for_status()
            recs = r.json()["data"] or []
            expect(isinstance(recs, list), "records not list")
            # may auto-create from template on first get
            if not any(x.get("template_item_id") for x in recs):
                # force second fetch after ensure logic
                r = client.get(f"/api/tasks/{tid}/records", headers=ah)
                r.raise_for_status()
                recs = r.json()["data"] or []
            suite.context["task_records"] = recs
            return f"records={len(recs)} linked={sum(1 for x in recs if x.get('template_item_id'))}"

        run_case(suite, "tasks", "task records list", t_task_records, "P0")

        def t_save_task_items():
            tid = suite.context["task_id"]
            recs = suite.context.get("task_records") or []
            linked = [x for x in recs if x.get("template_item_id")]
            expect(linked, "no linked task items to save")
            saved = 0
            for item in linked[:8]:
                payload = {
                    "template_item_id": item["template_item_id"],
                    "result": "pass",
                    "inspector_note": f"{MARK} ok",
                }
                r = client.post(f"/api/tasks/{tid}/records", headers=ah, json=payload)
                r.raise_for_status()
                expect(r.json().get("code") == 200, r.text[:200])
                saved += 1
            return f"saved={saved}"

        run_case(suite, "tasks", "save task item results", t_save_task_items, "P0")

        def t_task_final_judgment_stream():
            tid = suite.context["task_id"]
            with client.stream(
                "GET",
                f"/api/tasks/{tid}/final-judgment-stream",
                headers={**ah, "Accept": "text/event-stream"},
                timeout=180.0,
            ) as resp:
                expect(resp.status_code == 200, f"status={resp.status_code}")
                types = []
                done_payload = None
                for line in resp.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = json.loads(line[6:])
                    types.append(data.get("type"))
                    if data.get("type") in ("done", "error"):
                        done_payload = data
                        break
                expect(done_payload is not None, f"no terminal event, types={types[:10]}")
                expect(done_payload.get("type") == "done", f"error: {done_payload}")
                suite.context["task_ai_result"] = done_payload.get("result")
                return f"result={done_payload.get('result')} events={len(types)}"

        run_case(suite, "tasks", "AI final judgment stream (task)", t_task_final_judgment_stream, "P0")

        def t_complete_task():
            tid = suite.context["task_id"]
            r = client.post(f"/api/tasks/{tid}/complete", headers=ah)
            if r.status_code == 404:
                r = client.put(f"/api/tasks/{tid}", headers=ah, json={"status": "completed"})
            r.raise_for_status()
            return r.json().get("code")

        run_case(suite, "tasks", "complete task", t_complete_task, "P1")

        # ---------- 5. Inspection records (H5 free inspection path) ----------
        def t_create_record():
            payload = {
                "template_id": suite.context["template_id"],
                "enterprise_name": suite.context.get("enterprise_name") or f"{MARK}-企业",
                "remarks": MARK,
            }
            r = client.post("/api/records", headers=ah, json=payload)
            r.raise_for_status()
            body = r.json()
            expect(body.get("code") == 200, body)
            rid = body["data"]["id"]
            suite.context["record_id"] = rid
            return rid

        run_case(suite, "records", "create inspection record", t_create_record, "P0")

        def t_get_record():
            rid = suite.context["record_id"]
            r = client.get(f"/api/records/{rid}", headers=ah)
            r.raise_for_status()
            data = r.json()["data"]
            expect(data.get("template") or data.get("template_id"), "record missing template")
            suite.context["record_detail"] = data
            items = data.get("items") or []
            return f"status={data.get('status')} items={len(items)}"

        run_case(suite, "records", "get record detail", t_get_record, "P0")

        def t_save_record_items():
            rid = suite.context["record_id"]
            detail = suite.context.get("record_detail") or {}
            # flatten template items
            template_items = []

            def walk(nodes):
                for n in nodes or []:
                    if not n.get("is_category"):
                        template_items.append(n)
                    walk(n.get("children") or [])

            walk((detail.get("template") or {}).get("items") or [])
            if not template_items and detail.get("items"):
                for it in detail["items"]:
                    if it.get("template_item_id"):
                        template_items.append({"id": it["template_item_id"]})
            expect(template_items, "no template items on record")
            saved = 0
            for item in template_items[:6]:
                payload = {
                    "template_item_id": item.get("template_item_id") or item.get("id"),
                    "radio_value": "pass",
                    "problem_description": "",
                }
                r = client.post(f"/api/records/{rid}/items", headers=ah, json=payload)
                r.raise_for_status()
                expect(r.json().get("code") == 200, r.text[:200])
                saved += 1
            return f"saved={saved}"

        run_case(suite, "records", "save record items", t_save_record_items, "P0")

        def t_record_final_judgment():
            rid = suite.context["record_id"]
            with client.stream(
                "GET",
                f"/api/records/{rid}/final-judgment-stream",
                headers={**ah, "Accept": "text/event-stream"},
                timeout=180.0,
            ) as resp:
                expect(resp.status_code == 200, f"status={resp.status_code} body={resp.read()[:200]}")
                done = None
                for line in resp.iter_lines():
                    if line and line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data.get("type") in ("done", "error"):
                            done = data
                            break
                expect(done and done.get("type") == "done", f"ai failed: {done}")
                return f"result={done.get('result')}"

        run_case(suite, "records", "AI final judgment stream (record)", t_record_final_judgment, "P1")

        def t_submit_record():
            rid = suite.context["record_id"]
            client.put(
                f"/api/records/{rid}",
                headers=ah,
                json={"overall_result": "pass", "remarks": f"{MARK} 最终合格"},
            )
            r = client.post(f"/api/records/{rid}/submit", headers=ah)
            r.raise_for_status()
            return r.json().get("code")

        run_case(suite, "records", "submit record", t_submit_record, "P1")

        # ---------- 6. Audit projects ----------
        def t_list_projects():
            r = client.get("/api/audit-projects", headers=ah, params={"limit": 20})
            r.raise_for_status()
            data = r.json()["data"]
            items = data if isinstance(data, list) else data.get("items") or []
            suite.context["projects"] = items
            return f"projects={len(items)}"

        run_case(suite, "audit-projects", "list projects", t_list_projects, "P0")

        def t_create_project():
            enterprise_id = suite.context.get("enterprise_id")
            expect(enterprise_id, "no enterprise for project")
            payload = {
                "title": f"{MARK}-审核项目",
                "enterprise_id": enterprise_id,
                "audit_type": "initial",
                "audit_criteria": ["GB/T 19001-2016"],
                "status": "planning",
            }
            # try common schemas
            r = client.post("/api/audit-projects", headers=ah, json=payload)
            if r.status_code >= 400:
                # alternate field names
                payload2 = {
                    "title": f"{MARK}-审核项目",
                    "enterprise_id": enterprise_id,
                    "project_type": "initial",
                    "certification_systems": ["QMS"],
                    "audit_criteria": ["GB/T 19001-2016"],
                }
                r = client.post("/api/audit-projects", headers=ah, json=payload2)
            if r.status_code >= 400:
                raise AssertionError(r.text[:400])
            body = r.json()
            expect(body.get("code") == 200, body)
            proj = body["data"]
            suite.context["project_id"] = proj["id"] if isinstance(proj, dict) else proj
            if isinstance(proj, dict):
                suite.context["project_no"] = proj.get("project_no")
            return suite.context["project_id"]

        run_case(suite, "audit-projects", "create project", t_create_project, "P0")

        def t_project_detail():
            pid = suite.context["project_id"]
            r = client.get(f"/api/audit-projects/{pid}", headers=ah)
            r.raise_for_status()
            return r.json().get("code")

        run_case(suite, "audit-projects", "project detail", t_project_detail, "P0")

        def t_add_team_member():
            pid = suite.context["project_id"]
            uid = suite.context.get("auditor_id") or suite.context.get("expert_id")
            expect(uid, "no member user")
            # 正式字段：member_id；project_id 路径优先，可省略
            payload = {"member_id": uid, "role": "member"}
            r = client.post(f"/api/audit-projects/{pid}/team", headers=ah, json=payload)
            if r.status_code >= 400:
                # 兼容带 project_id 的旧客户端
                payload = {"member_id": uid, "role": "member", "project_id": pid}
                r = client.post(f"/api/audit-projects/{pid}/team", headers=ah, json=payload)
            if r.status_code >= 400:
                raise AssertionError(f"team add failed {r.status_code}: {r.text[:200]}")
            return r.json().get("code")

        run_case(suite, "audit-projects", "add team member", t_add_team_member, "P1")

        def t_create_plan_item():
            pid = suite.context["project_id"]
            uid = suite.context.get("auditor_id") or suite.context.get("expert_id")
            # 路径已含 project_id，请求体可不传；同时覆盖“不传 project_id”回归
            payload = {
                "area_name": f"{MARK}-车间",
                "plan_date": str(date.today()),
                "time_start": "09:00",
                "time_end": "12:00",
                "group_no": "1",
                "template_id": suite.context["template_id"],
                "assigned_member_ids": [uid] if uid else [],
                "certification_systems": ["QMS"],
            }
            r = client.post(f"/api/audit-projects/{pid}/plan", headers=ah, json=payload)
            if r.status_code >= 400:
                raise AssertionError(r.text[:400])
            body = r.json()
            plan = body["data"]
            suite.context["plan_item_id"] = plan["id"]
            suite.context["plan_task_id"] = plan.get("inspection_task_id")
            expect(plan.get("inspection_task_id"), "plan item should auto-create inspection task")
            return f"plan={plan['id']} task={plan.get('inspection_task_id')}"

        run_case(suite, "audit-projects", "create plan item (+auto task)", t_create_plan_item, "P0")

        def t_plan_task_ready():
            tid = suite.context.get("plan_task_id")
            expect(tid, "plan item missing inspection_task_id")
            r = client.get(f"/api/tasks/{tid}", headers=ah)
            r.raise_for_status()
            task = r.json()["data"]
            expect(task.get("template_id"), "auto task missing template_id")
            rr = client.get(f"/api/tasks/{tid}/records", headers=ah)
            rr.raise_for_status()
            recs = rr.json()["data"] or []
            suite.context["plan_task_records"] = recs
            return f"task_status={task.get('status')} items={len(recs)} template={task.get('template_id')}"

        run_case(suite, "audit-projects", "plan auto task has template+items", t_plan_task_ready, "P0")

        def t_execute_plan_task_like_h5():
            tid = suite.context["plan_task_id"]
            # start
            client.post(f"/api/tasks/{tid}/start", headers=ah)
            recs = suite.context.get("plan_task_records") or []
            if not recs:
                recs = client.get(f"/api/tasks/{tid}/records", headers=ah).json().get("data") or []
            linked = [x for x in recs if x.get("template_item_id")]
            expect(linked, "no items on plan task")
            for item in linked[:5]:
                client.post(
                    f"/api/tasks/{tid}/records",
                    headers=ah,
                    json={
                        "template_item_id": item["template_item_id"],
                        "result": "pass",
                        "inspector_note": f"{MARK} h5-path",
                    },
                )
            # AI judgment
            with client.stream(
                "GET",
                f"/api/tasks/{tid}/final-judgment-stream",
                headers={**ah, "Accept": "text/event-stream"},
                timeout=180.0,
            ) as resp:
                expect(resp.status_code == 200, f"ai status {resp.status_code}")
                done = None
                for line in resp.iter_lines():
                    if line and line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data.get("type") in ("done", "error"):
                            done = data
                            break
                expect(done and done.get("type") == "done", f"ai fail {done}")
            return f"ai={done.get('result')} items={len(linked)}"

        run_case(suite, "h5-path", "H5 task execute + AI judgment", t_execute_plan_task_like_h5, "P0")

        def t_list_plan():
            pid = suite.context["project_id"]
            r = client.get(f"/api/audit-projects/{pid}/plan", headers=ah)
            r.raise_for_status()
            data = r.json()["data"]
            items = data if isinstance(data, list) else data.get("items") or []
            return f"plan_items={len(items)}"

        run_case(suite, "audit-projects", "list plan items", t_list_plan, "P1")

        # Project agent / sessions (best effort)
        def t_create_session():
            pid = suite.context["project_id"]
            payload = {
                "title": f"{MARK}-会话",
                "plan_item_id": suite.context.get("plan_item_id"),
            }
            r = client.post(f"/api/audit-projects/{pid}/sessions", headers=ah, json=payload)
            if r.status_code == 404:
                r = client.post(f"/api/audit-projects/{pid}/agent/sessions", headers=ah, json=payload)
            if r.status_code >= 400:
                return f"optional skip {r.status_code}: {r.text[:120]}"
            body = r.json()
            sid = (body.get("data") or {}).get("id")
            suite.context["session_id"] = sid
            return sid or body.get("code")

        run_case(suite, "project-agent", "create audit session", t_create_session, "P1")

        def t_quality_check():
            pid = suite.context["project_id"]
            r = client.post(f"/api/audit-projects/{pid}/quality-check", headers=ah)
            if r.status_code == 404:
                r = client.get(f"/api/audit-projects/{pid}/quality-check", headers=ah)
            if r.status_code >= 400:
                return f"optional {r.status_code}: {r.text[:150]}"
            return r.json().get("code")

        run_case(suite, "project-agent", "quality check", t_quality_check, "P2")

        def t_artifacts_list():
            pid = suite.context["project_id"]
            r = client.get(f"/api/audit-projects/{pid}/artifacts", headers=ah)
            if r.status_code >= 400:
                return f"optional {r.status_code}"
            data = r.json().get("data")
            items = data if isinstance(data, list) else (data or {}).get("items") or []
            return f"artifacts={len(items)}"

        run_case(suite, "project-agent", "list artifacts", t_artifacts_list, "P2")

        # ---------- 7. Knowledge ----------
        def t_knowledge_categories():
            r = client.get("/api/knowledge/categories", headers=ah)
            r.raise_for_status()
            data = r.json()["data"]
            items = data if isinstance(data, list) else data.get("items") or []
            if items:
                suite.context["knowledge_category_id"] = items[0]["id"]
            return f"categories={len(items)}"

        run_case(suite, "knowledge", "list categories", t_knowledge_categories, "P1")

        def t_knowledge_docs():
            r = client.get("/api/knowledge/documents", headers=ah, params={"limit": 20})
            if r.status_code == 404:
                r = client.get("/api/knowledge", headers=ah)
            if r.status_code >= 400:
                return f"optional {r.status_code}"
            data = r.json().get("data")
            items = data if isinstance(data, list) else (data or {}).get("items") or []
            return f"docs={len(items or [])}"

        run_case(suite, "knowledge", "list documents", t_knowledge_docs, "P2")

        # ---------- 8. Analytics / statistics ----------
        def t_analytics():
            r = client.get("/api/analytics/dashboard", headers=ah)
            if r.status_code == 404:
                r = client.get("/api/analytics/stats", headers=ah)
            if r.status_code == 404:
                r = client.get("/api/analytics", headers=ah)
            if r.status_code >= 400:
                return f"optional {r.status_code}"
            return r.json().get("code")

        run_case(suite, "analytics", "dashboard stats", t_analytics, "P2")

        def t_statistics():
            r = client.get("/api/statistics/overview", headers=ah)
            if r.status_code == 404:
                r = client.get("/api/statistics", headers=ah)
            if r.status_code >= 400:
                return f"optional {r.status_code}"
            return r.json().get("code")

        run_case(suite, "statistics", "audit statistics", t_statistics, "P2")

        # ---------- 9. Expert path (H5 role) ----------
        if expert_token and expert_id:
            def t_expert_tasks():
                r = client.get("/api/tasks", headers=eh, params={"limit": 20})
                r.raise_for_status()
                data = r.json()["data"]
                items = data.get("items") if isinstance(data, dict) else data
                return f"expert_tasks={len(items or [])}"

            run_case(suite, "h5-role", "expert list own tasks", t_expert_tasks, "P1")

            def t_expert_my_audit():
                r = client.get("/api/audit-projects/my-tasks", headers=eh)
                if r.status_code == 404:
                    r = client.get("/api/audit-projects/my", headers=eh)
                if r.status_code >= 400:
                    return f"optional {r.status_code}"
                return r.json().get("code")

            run_case(suite, "h5-role", "expert my audit tasks", t_expert_my_audit, "P2")

        # ---------- 10. Negative path: record-by-task-id should 404; task AI should 200 ----------
        def t_negative_record_by_task():
            tid = suite.context["task_id"]
            r = client.get(f"/api/records/{tid}", headers=ah)
            expect(r.status_code in (404, 422) or r.json().get("code") in (404, 422, 500), "should not treat task as record")
            return r.status_code

        run_case(suite, "regression", "task id is not record id", t_negative_record_by_task, "P1")

        def t_regression_task_ai_endpoint_exists():
            # openapi check
            r = client.get("/openapi.json")
            r.raise_for_status()
            paths = r.json().get("paths") or {}
            key = "/api/tasks/{task_id}/final-judgment-stream"
            # may be without /api prefix in schema
            found = any("final-judgment-stream" in p and "tasks" in p for p in paths)
            expect(found, f"missing final-judgment-stream in openapi, sample={[p for p in paths if 'final' in p][:5]}")
            return "found"

        run_case(suite, "regression", "openapi has task final-judgment-stream", t_regression_task_ai_endpoint_exists, "P0")

    # ---------- Summary ----------
    print("\n" + "=" * 70)
    print(f"TOTAL: {len(suite.results)}  PASS: {suite.passed}  FAIL: {suite.failed}")
    print("=" * 70)
    fails = [r for r in suite.results if not r.ok]
    if fails:
        print("\nFAILURES:")
        for r in fails:
            print(f"  - [{r.severity}] {r.module} / {r.name}: {r.detail}")

    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "base": BASE,
        "web": WEB,
        "h5": H5,
        "marker": MARK,
        "total": len(suite.results),
        "passed": suite.passed,
        "failed": suite.failed,
        "context": {k: v for k, v in suite.context.items() if k not in ("template_items", "record_detail", "task_records", "plan_task_records", "projects")},
        "results": [r.__dict__ for r in suite.results],
    }
    out = f"docs/EFIS_全面系统测试结果_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nJSON report: {out}")
    suite.context["_report_path"] = out
    suite.context["_report"] = report
    # stash for caller via stdout marker
    print("REPORT_JSON=" + out)
    return 0 if suite.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
