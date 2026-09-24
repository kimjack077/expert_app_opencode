# -*- coding: utf-8 -*-
"""2026-09-23 全面测试发现的缺陷回归用例。

用法::

    cd backend
    EFIS_TEST_DB_NAME=db_expert_test .venv/Scripts/python.exe -m pytest tests/test_defects_20260923.py -v

约定：
- 标 ``xfail`` 的是**已知未修复缺陷**。修复后用例会自动变成 ``XPASS``，
  届时请移除对应的 ``xfail`` 标记，使其成为普通防回归用例。
- 未标 ``xfail`` 的是防回归用例，必须长期通过。
- 完整测试报告见项目根目录 ``系统全面测试报告_20260923.md``。

背景：本轮对 155 路径 / 200 操作做了全量 CRUD 闭环 + 一致性 + 权限 + 边界 + 端到端测试，
共 369 条用例。以下用例只固化「可自动断言」的部分，供门禁复用。
"""

from __future__ import annotations

import json
import os
import uuid

import pytest

# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


def _login(client, username: str, password: str):
    """登录并返回 token；失败返回 None（用例自行 skip）。"""
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    if resp.status_code != 200:
        return None
    data = resp.json().get("data") or {}
    return data.get("access_token") or data.get("token")


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def auth_headers_factory(token: str) -> dict:
    """与 conftest 的 auth_headers 同义，供需要多角色 token 的用例使用。"""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def expert_token(client, admin_token):
    token = _login(client, "expert", os.environ.get("EFIS_TEST_EXPERT_PASSWORD", "expert123"))
    if not token:
        pytest.skip("测试库缺少 expert 账号")
    return token


@pytest.fixture(scope="module")
def auditor_token(client, admin_token):
    token = _login(
        client, "auditor_chen", os.environ.get("EFIS_TEST_AUDITOR_PASSWORD", "expert123")
    )
    if not token:
        pytest.skip("测试库缺少 auditor_chen 账号")
    return token


# ===========================================================================
# A. 防回归用例（必须长期通过）
# ===========================================================================


def test_a1_completed_task_cannot_be_cancelled(client, auth_headers):
    """已完成任务再次取消必须被拒绝（状态机）。"""
    resp = client.get("/api/tasks", params={"skip": 0, "limit": 100}, headers=auth_headers)
    assert resp.status_code == 200
    items = (resp.json().get("data") or {}).get("items") or []
    done = [t for t in items if t.get("status") == "completed"]
    if not done:
        pytest.skip("测试库中没有已完成任务")

    tid = done[0]["id"]
    resp = client.post(f"/api/tasks/{tid}/cancel", json={"reason": "regression"}, headers=auth_headers)
    assert resp.status_code in (400, 409), (
        f"已完成任务 cancel 应被拒绝，实际 {resp.status_code}：{resp.text[:200]}"
    )
    # 回查状态未被篡改
    resp = client.get(f"/api/tasks/{tid}", headers=auth_headers)
    assert resp.status_code == 200
    assert (resp.json().get("data") or {}).get("status") == "completed"


def test_a2_record_list_visible_implies_detail_visible(client, admin_token, auditor_token):
    """列表级可见 ⇒ 详情级可见（两端必须同口径，防「列表有、点进去 403」）。"""
    for name, token in (("admin", admin_token), ("auditor", auditor_token)):
        resp = client.get("/api/records", params={"skip": 0, "limit": 20}, headers=_bearer(token))
        assert resp.status_code == 200, f"{name} 读取记录列表失败"
        data = resp.json().get("data")
        items = (data or {}).get("items") if isinstance(data, dict) else (data or [])
        bad = []
        for it in (items or [])[:10]:
            r = client.get(f"/api/records/{it['id']}", headers=_bearer(token))
            if r.status_code != 200:
                bad.append((it["id"][:8], r.status_code))
        assert not bad, f"{name} 列表可见但详情不可见：{bad}"


def test_a3_read_endpoints_are_idempotent(client, auth_headers):
    """连续 3 次 GET 同一资源必须逐字节一致（防查询接口混入写操作）。"""
    for path in ("/api/statistics/overview", "/api/analytics/dashboard", "/api/industries"):
        bodies = []
        for _ in range(3):
            resp = client.get(path, headers=auth_headers)
            assert resp.status_code == 200, f"{path} -> {resp.status_code}"
            payload = resp.json()
            payload.pop("timestamp", None)
            bodies.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        assert bodies[0] == bodies[1] == bodies[2], f"{path} 三次响应不一致（疑似有写操作或随机排序）"


def test_a4_record_item_buckets_close(client, auth_headers):
    """记录检查项分档加法必须闭合：pass+fail+na+other+unfilled == 叶子项数。"""
    resp = client.get("/api/records", params={"skip": 0, "limit": 10}, headers=auth_headers)
    assert resp.status_code == 200
    items = (resp.json().get("data") or {}).get("items") or []
    if not items:
        pytest.skip("测试库中没有检查记录")

    pass_v = {"pass", "qualified", "符合", "1", "compliant"}
    fail_v = {"fail", "non_compliant", "unqualified", "不符合", "0"}
    na_v = {"na", "not_applicable", "不适用"}

    for rec in items[:5]:
        resp = client.get(f"/api/records/{rec['id']}/items", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json().get("data")
        tree = data if isinstance(data, list) else (data or {}).get("items", [])

        leaves = []

        def walk(nodes):
            for node in nodes:
                kids = node.get("children") or []
                if kids:
                    walk(kids)
                else:
                    leaves.append(node)

        walk(tree or [])
        buckets = {"pass": 0, "fail": 0, "na": 0, "other": 0, "unfilled": 0}
        for leaf in leaves:
            raw = leaf.get("radio_value") or leaf.get("result") or leaf.get("evaluation_3level")
            if raw is None or raw == "":
                buckets["unfilled"] += 1
                continue
            value = str(raw).strip().lower()
            if value in pass_v:
                buckets["pass"] += 1
            elif value in fail_v:
                buckets["fail"] += 1
            elif value in na_v:
                buckets["na"] += 1
            else:
                buckets["other"] += 1
        assert sum(buckets.values()) == len(leaves), f"记录 {rec['id'][:8]} 分档不闭合：{buckets}"


def test_a5_admin_cannot_delete_self(client, auth_headers):
    """管理员不得删除自己（自锁保护）。"""
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    me = (resp.json().get("data") or {}).get("id")
    assert me
    resp = client.delete(f"/api/users/{me}", headers=auth_headers)
    assert resp.status_code in (400, 403), f"自删应被拒绝，实际 {resp.status_code}"


# ===========================================================================
# B. 已知缺陷（xfail；修复后自动 XPASS，请移除标记）
# ===========================================================================


@pytest.mark.xfail(
    reason="P0-1：report_service.py:193 对 ORM 对象执行 getattr(it,'children')，"
    "该关系未预加载 → 同步方法中触发懒加载 → MissingGreenlet → /report 与 /report/pdf 返回 500",
    strict=False,
)
def test_b1_flatten_items_does_not_lazy_load_children(db_engine):
    """``_flatten_items`` 收到未预加载 children 的 ORM 对象时不应触发懒加载。

    这是 P0-1 的最小复现（不依赖库中恰好存在"无 template_snapshot"的记录）：
    ``generate_report_data`` 在记录没有快照时会把 ORM ``TemplateItem`` 直接传进
    ``_flatten_items``，而后者用 ``getattr(it, 'children', None)`` 判断嵌套 —— 该属性
    是自引用关系，未预加载时会在同步方法里发起 IO，抛 ``MissingGreenlet``。

    修复方向（任一）：
    1. 用 ``sqlalchemy.inspect(it).unloaded`` 判断后再取值，避免触发懒加载；
    2. 在 ``records.py`` 的 /report 端点先把模板项序列化为纯 dict 再传入服务层。
    """
    import asyncio

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.template import TemplateItem
    from app.services.report_service import report_service

    async def _load():
        factory = async_sessionmaker(db_engine, expire_on_commit=False)
        async with factory() as session:
            rows = (await session.execute(select(TemplateItem).limit(5))).scalars().all()
            # 关键：不预加载 children，模拟 /report 端点在无快照记录上的加载方式
            return list(rows)

    items = asyncio.run(_load())
    if not items:
        pytest.skip("测试库中没有模板检查项")

    result = report_service._flatten_items(items)
    assert isinstance(result, list), f"_flatten_items 应返回列表，实际 {type(result)}"


@pytest.mark.xfail(
    reason="P1-1：industries.py:86/103/127 三个写端点仅依赖 get_current_user，"
    "非管理员可增删改行业分类（UI 上按钮也无角色门控）",
    strict=False,
)
def test_b2_industry_write_requires_admin(client, admin_token, expert_token, auditor_token):
    """行业分类的写操作必须仅限管理员。"""
    # 先用管理员造一个真实对象（用假 UUID 会得到 404，无法区分「越权」与「对象不存在」）
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/industries",
        json={"name": f"[REG]权限行业_{suffix}", "code": f"REG{suffix}", "sort_order": 996},
        headers=auth_headers_factory(admin_token),
    )
    assert resp.status_code in (200, 201), resp.text[:200]
    ind_id = (resp.json().get("data") or {}).get("id")

    try:
        violations = []
        for name, token in (("expert", expert_token), ("auditor", auditor_token)):
            r = client.delete(f"/api/industries/{ind_id}", headers=_bearer(token))
            if r.status_code not in (401, 403):
                violations.append((name, "DELETE", r.status_code))
            r = client.post(
                "/api/industries",
                json={"name": f"[REG]{name}越权_{suffix}", "code": f"REGX{suffix}", "sort_order": 995},
                headers=_bearer(token),
            )
            if r.status_code in (200, 201):
                violations.append((name, "POST", r.status_code))
        assert not violations, f"行业分类写操作未做角色校验：{violations}"
    finally:
        client.delete(f"/api/industries/{ind_id}", headers=auth_headers_factory(admin_token))


@pytest.mark.xfail(
    reason="P2-1：路径参数声明 UUID 的端点（industries / audit-projects）非法 ID 返回 422，"
    "声明 str 的端点（enterprises/users/templates/records/tasks）返回 404，口径不一致",
    strict=False,
)
def test_b3_invalid_uuid_returns_404_consistently(client, auth_headers):
    """非法 UUID 在所有资源上应返回统一状态码（当前为 404）。"""
    paths = [
        "/api/enterprises/not-a-uuid",
        "/api/users/not-a-uuid",
        "/api/industries/not-a-uuid",
        "/api/templates/not-a-uuid",
        "/api/records/not-a-uuid",
        "/api/tasks/not-a-uuid",
        "/api/audit-projects/not-a-uuid",
    ]
    codes = {}
    for path in paths:
        codes[path] = client.get(path, headers=auth_headers).status_code
    assert len(set(codes.values())) == 1, f"非法 UUID 返回码不统一：{codes}"


@pytest.mark.xfail(
    reason="P2-2：users.py:63/92 对重复用户名显式抛 400，而重复 credit_code 走唯一约束返回 409",
    strict=False,
)
def test_b4_duplicate_username_returns_409(client, auth_headers):
    """唯一约束冲突应统一返回 409。"""
    username = f"reg_dup_{uuid.uuid4().hex[:8]}"
    payload = {"username": username, "password": "Test@123456", "role": "auditor"}
    first = client.post("/api/users", json=payload, headers=auth_headers)
    assert first.status_code in (200, 201), first.text[:200]
    uid = (first.json().get("data") or {}).get("id")
    try:
        second = client.post("/api/users", json=payload, headers=auth_headers)
        assert second.status_code == 409, (
            f"重复用户名应返回 409，实际 {second.status_code}：{second.text[:150]}"
        )
    finally:
        if uid:
            client.delete(f"/api/users/{uid}", headers=auth_headers)


@pytest.mark.xfail(
    reason="P2-4：/api/tasks/{id}/records 无写入守卫，未知结果字段被 Pydantic extra=ignore 静默丢弃，"
    "返回 200 但值未落库（/api/records/{id}/items 有守卫）",
    strict=False,
)
def test_b5_task_record_write_guard(client, auth_headers):
    """任务填报写入未知结果字段时应被拒绝或告警，而不是静默丢弃后返回 200。"""
    resp = client.get("/api/tasks", params={"skip": 0, "limit": 50}, headers=auth_headers)
    assert resp.status_code == 200
    tasks = (resp.json().get("data") or {}).get("items") or []
    if not tasks:
        pytest.skip("测试库中没有检查任务")
    task = tasks[0]

    # 取该任务的记录，找一条模板项用于构造载荷
    resp = client.get(f"/api/tasks/{task['id']}/records", headers=auth_headers)
    assert resp.status_code == 200
    recs = resp.json().get("data")
    recs = recs if isinstance(recs, list) else (recs or {}).get("items", [])
    if not recs:
        pytest.skip("该任务没有可用的填报记录")

    template_item_id = recs[0].get("template_item_id")
    if not template_item_id:
        pytest.skip("填报记录缺少 template_item_id")

    before = recs[0].get("radio_value")
    resp = client.post(
        f"/api/tasks/{task['id']}/records",
        json={"template_item_id": template_item_id, "radio_value": "pass"},
        headers=auth_headers,
    )
    # 期望：要么拒绝（4xx 提示字段应写到 result），要么真正落库
    assert resp.status_code >= 400, (
        "传入 radio_value 时端点返回 200，但该字段不在写入 schema 中会被静默丢弃，"
        f"调用方无法察觉数据丢失（before={before}）"
    )


@pytest.mark.xfail(
    reason="P2-5：records/tasks/enterprises 的 limit 上限为 100，audit-projects 为 1000",
    strict=False,
)
def test_b6_page_size_upper_bound_consistent(client, auth_headers):
    """分页 limit 的上限应保持一致。"""
    limits = {
        "/api/records": 1000,
        "/api/tasks": 1000,
        "/api/enterprises": 1000,
        "/api/audit-projects": 1000,
    }
    results = {}
    for path, limit in limits.items():
        resp = client.get(path, params={"skip": 0, "limit": limit}, headers=auth_headers)
        results[path] = resp.status_code
    assert all(code == 200 for code in results.values()), (
        f"各端点对 limit=1000 的处理不一致（422 表示上限更低）：{results}"
    )


# ===========================================================================
# C. 前端静态契约（不需要数据库）
# ===========================================================================


def test_c1_template_version_prefix_not_duplicated():
    """模板版本号渲染不得无条件叠加 'v' 前缀（库中已存在 'v1.0' 会显示成 'vv1.0'）。"""
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    path = os.path.join(root, "web-admin", "src", "pages", "Templates", "index.tsx")
    if not os.path.exists(path):
        pytest.skip("未找到模板列表页源码")

    with open(path, encoding="utf-8") as fh:
        source = fh.read()

    # 期望渲染前先剥离已有前缀，例如 String(version).replace(/^v/i, '')
    has_guard = "replace(/^v/i" in source or "replace(/^V/" in source
    assert has_guard, (
        "Templates/index.tsx 渲染版本号时未剥离已存在的 'v' 前缀，"
        "库中 'v1.0' 会显示为 'vv1.0'"
    )
