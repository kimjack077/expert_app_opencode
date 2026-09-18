"""接口层测试：软删除级联在**真实数据库**上是否真的生效。

═══════════════════════════════════════════════════════════════════════════
 为什么契约层测试不够
═══════════════════════════════════════════════════════════════════════════
``test_soft_delete_cascade.py`` 只验证**策略表的完备性与自洽**——
它读 SQLAlchemy 元数据，不碰数据库。策略登记得再对，
如果端点没接线、或者 ``RETURNING id`` 在 asyncpg 上跑不通，
线上照样留孤儿。

本文件补上这一段：真的建数据、真的调删除接口、真的回查数据库。

═══════════════════════════════════════════════════════════════════════════
 守住的四条
═══════════════════════════════════════════════════════════════════════════
1. **检查记录删除** → ``inspection_record_items``（硬删除表）真的被清掉
   （实测线上已积压 189 条永久孤儿）
2. **记录本身仍可恢复** → 软删除，不是物理删除
3. **模板删除不毁历史** → 引用该模板的检查记录仍可访问（PRESERVE 约定）
4. **项目删除清干净** → 计划项软删 + 检查任务软删（间接级联）+
   任务明细硬删（实测 186 条孤儿）

═══════════════════════════════════════════════════════════════════════════
 运行前提
═══════════════════════════════════════════════════════════════════════════
需先把 ``EFIS_TEST_DB_NAME`` 指向独立测试库（见 conftest.py）。
未配置时全部自动 skip —— 本地与生产共用同一个远程库，裸跑会写脏生产数据。

    set EFIS_TEST_DB_NAME=db_expert_test
    .venv\\Scripts\\python.exe -m pytest tests/test_api_soft_delete_cascade.py -v
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

pytestmark = pytest.mark.api

RADIO_OPTIONS = {
    "options": [
        {"value": "pass", "label": "合格"},
        {"value": "fail", "label": "不合格"},
        {"value": "na", "label": "不适用"},
    ]
}


def _data(resp):
    """解开统一响应体 ``{code, message, data, timestamp}``。"""
    assert resp.status_code in (200, 201), f"HTTP {resp.status_code}: {resp.text[:400]}"
    payload = resp.json()
    assert payload.get("code") in (0, 200, "0", "200", None), f"业务码异常: {payload}"
    return payload.get("data")


# ---------------------------------------------------------------------------
# 直连数据库回查
# ---------------------------------------------------------------------------
# 为什么不复用 conftest 的 session 级 engine：asyncpg 连接池绑定在创建它的事件
# 循环上，跨循环使用会报 "got Future attached to a different loop"。
# 这里用 NullPool + 一次性 engine，跑完即 dispose，与 TestClient 的循环互不干扰。


def _db_query(sql: str, params: dict | None = None):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config import settings

    async def _run():
        engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text(sql), params or {})
                return result.fetchall()
        finally:
            await engine.dispose()

    return asyncio.run(_run())


def _scalar(sql: str, params: dict | None = None):
    rows = _db_query(sql, params)
    return rows[0][0] if rows else None


def _is_deleted(table: str, row_id: str) -> bool | None:
    """回查某行是否已被软删；行不存在返回 ``None``。"""
    return _scalar(f"select is_deleted from {table} where id = :id", {"id": row_id})


def _count(table: str, column: str, value) -> int:
    return int(_scalar(f"select count(*) from {table} where {column} = :v", {"v": value}) or 0)


# ---------------------------------------------------------------------------
# 造数
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cascade_template(client, auth_headers):
    """模块级：一个模板 + 两个 radio 叶子检查项。

    叶子项是必需的 —— ``create_plan_item`` 只会为非分类的叶子项生成
    ``task_item_records``，没有叶子项就测不到"任务明细随任务清除"。
    """
    suffix = uuid4().hex[:8]

    template = _data(
        client.post(
            "/api/templates",
            json={
                "name": f"E2E_TEST_级联模板_{suffix}",
                "code": f"E2ECASCADE_{suffix}",
                "description": "自动化测试：软删除级联",
            },
            headers=auth_headers,
        )
    )
    template_id = template["id"]

    items = {}
    for tag in ("a", "b"):
        item = _data(
            client.post(
                f"/api/templates/{template_id}/items",
                json={
                    "title": f"E2E_TEST_级联检查项_{tag}_{suffix}",
                    "check_type": "radio",
                    "is_category": False,
                    "sort_order": 0,
                    "result_options": RADIO_OPTIONS,
                },
                headers=auth_headers,
            )
        )
        items[tag] = item["id"]

    yield {"template_id": template_id, "items": items}

    # 清理必须复用 session 级 client（新建会触发事件循环冲突）
    try:
        client.delete(f"/api/templates/{template_id}", headers=auth_headers)
    except Exception:  # noqa: BLE001 — 清理失败不应让用例报错
        pass


def _new_record(client, auth_headers, template_id, enterprise_id) -> str:
    record = _data(
        client.post(
            "/api/records",
            json={"template_id": template_id, "enterprise_id": enterprise_id},
            headers=auth_headers,
        )
    )
    return record["id"]


# ---------------------------------------------------------------------------
# 1. 检查记录 → 明细（硬删除表）
# ---------------------------------------------------------------------------


def test_delete_record_hard_removes_its_item_rows(
    client, auth_headers, cascade_template, shared_enterprise_id, cleanup_registry
):
    """删除检查记录后，``inspection_record_items`` 的明细必须真的消失。

    该表**没有 is_deleted 列**，是硬删除表。记录软删后明细若不清，
    就成了永久孤儿：既不再展示、也没有任何路径能清理（实测线上积压 189 条）。
    ORM 上已声明 ``cascade="all, delete-orphan"``，说明设计意图本就是随记录删除。
    """
    record_id = _new_record(
        client, auth_headers, cascade_template["template_id"], shared_enterprise_id
    )
    cleanup_registry.append(("records", record_id))

    for tag in ("a", "b"):
        resp = client.post(
            f"/api/records/{record_id}/items",
            json={
                "template_item_id": cascade_template["items"][tag],
                "check_type": "radio",
                "radio_value": "pass",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text[:300]

    before = _count("inspection_record_items", "record_id", record_id)
    assert before >= 2, f"前置条件不成立：明细应有 2 条，实际 {before}"

    resp = client.delete(f"/api/records/{record_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text[:300]

    cascaded = (_data(resp) or {}).get("cascaded") or {}
    assert cascaded.get("inspection_record_items", 0) >= 2, (
        "删除响应必须报告级联影响行数，供前端提示与审计日志使用；"
        f"实际 cascaded={cascaded}"
    )

    after = _count("inspection_record_items", "record_id", record_id)
    assert after == 0, (
        f"记录已删但仍有 {after} 条明细残留 —— 这些是永久孤儿（该表无 is_deleted 列）"
    )


def test_deleted_record_is_recoverable_not_destroyed(
    client, auth_headers, cascade_template, shared_enterprise_id, cleanup_registry
):
    """记录本身必须**软删**（可恢复），级联只清明细，不动记录。

    若记录被物理删除，误删就不可逆了 —— 这与 CASCADE_SOFT 的设计意图相悖。
    """
    record_id = _new_record(
        client, auth_headers, cascade_template["template_id"], shared_enterprise_id
    )
    cleanup_registry.append(("records", record_id))

    assert client.delete(
        f"/api/records/{record_id}", headers=auth_headers
    ).status_code == 200

    assert _is_deleted("inspection_records", record_id) is True, (
        "记录应被软删（is_deleted=True），行本身仍存在于库中，可恢复"
    )


# ---------------------------------------------------------------------------
# 2. 模板 → 历史记录（PRESERVE，端到端）
# ---------------------------------------------------------------------------


def test_delete_template_preserves_history_records(
    client, auth_headers, shared_enterprise_id, cleanup_registry
):
    """**回归护栏**：删除模板不得销毁引用它的历史检查记录。

    ``delete_template`` 的文档明确承诺「历史检查记录、审核计划等引用此模板的
    记录仍可正常访问」。本用例把这句话变成断言 —— 端到端（真的删模板、
    真的回查记录接口），而不是只看策略表里的一个常量。
    """
    suffix = uuid4().hex[:8]

    template_id = _data(
        client.post(
            "/api/templates",
            json={
                "name": f"E2E_TEST_模板保留_{suffix}",
                "code": f"E2EKEEP_{suffix}",
                "description": "自动化测试：模板删除保留历史",
            },
            headers=auth_headers,
        )
    )["id"]

    record_id = _new_record(
        client, auth_headers, template_id, shared_enterprise_id
    )
    cleanup_registry.append(("records", record_id))

    resp = client.delete(f"/api/templates/{template_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text[:300]

    # 记录仍存活
    assert _is_deleted("inspection_records", record_id) is False, (
        "删除模板后历史检查记录被连带删除 —— 这会让客户的历史审核数据凭空消失，"
        "属最高危改动。inspection_records.template_id 必须 PRESERVE。"
    )

    # 记录接口仍可访问
    detail = client.get(f"/api/records/{record_id}", headers=auth_headers)
    assert detail.status_code == 200, (
        f"删除模板后记录详情不可访问（HTTP {detail.status_code}）——"
        "与 delete_template 的文档承诺不符"
    )


# ---------------------------------------------------------------------------
# 3. 审核项目 → 计划项 + 检查任务（含间接级联）
# ---------------------------------------------------------------------------


def test_delete_audit_project_cascades_plan_items_and_tasks(
    client, auth_headers, cascade_template, shared_enterprise_id, cleanup_registry
):
    """删除审核项目后：计划项软删、检查任务软删、任务明细硬删。

    覆盖两条规则：

    * ``audit_plan_items.project_id`` → CASCADE_SOFT（直接级联）
    * 「删项目 → 删检查任务」→ 间接级联。外键在计划项一侧，
      FK 图推导不出来，必须显式登记在 ``INDIRECT_CASCADE_POLICY``。
      否则任务会留在审核员的「我的任务」列表里，且因计划项已软删而
      回填不到 ``audit_project_id`` / ``area_name``，卡片失去全部上下文。
    """
    suffix = uuid4().hex[:8]

    project_id = _data(
        client.post(
            "/api/audit-projects",
            json={
                "title": f"E2E_TEST_级联项目_{suffix}",
                "enterprise_id": shared_enterprise_id,
                "audit_type": "initial",
                "certification_systems": ["Q"],
            },
            headers=auth_headers,
        )
    )["id"]
    cleanup_registry.append(("audit-projects", project_id))

    plan = _data(
        client.post(
            f"/api/audit-projects/{project_id}/plan",
            json={
                "plan_date": "2026-09-20",
                "area_name": f"E2E_TEST_区域_{suffix}",
                "assigned_member_ids": [],
                "template_id": cascade_template["template_id"],
            },
            headers=auth_headers,
        )
    )
    plan_item_id = plan["id"]
    task_id = plan["inspection_task_id"]
    assert task_id, "create_plan_item 应自动创建检查任务，否则本用例前提不成立"

    # 前置：全部是活的
    assert _is_deleted("audit_plan_items", plan_item_id) is False
    assert _is_deleted("inspection_tasks", task_id) is False
    task_item_count = _count("task_item_records", "task_id", task_id)
    assert task_item_count >= 1, (
        f"前置条件不成立：模板有叶子项，任务明细应有记录，实际 {task_item_count}"
    )

    resp = client.delete(f"/api/audit-projects/{project_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text[:300]
    cascaded = (_data(resp) or {}).get("cascaded") or {}

    # 计划项：软删（可逆）
    assert _is_deleted("audit_plan_items", plan_item_id) is True, (
        "计划项未随项目软删 —— 「我的审核任务」会列出这些计划项，点进去必定 404"
        "（外部测试 P0-29）"
    )
    assert cascaded.get("audit_plan_items", 0) >= 1, f"响应未报告计划项级联：{cascaded}"

    # 检查任务：间接级联软删
    assert _is_deleted("inspection_tasks", task_id) is True, (
        "检查任务未随项目软删 —— 任务会留在「我的任务」列表里，"
        "且因计划项已软删而失去 audit_project_id / area_name，卡片没有上下文。\n"
        "该关系在 FK 图上不存在，需登记在 INDIRECT_CASCADE_POLICY。"
    )
    assert cascaded.get("inspection_tasks", 0) >= 1, f"响应未报告任务级联：{cascaded}"

    # 任务明细：硬删（无 is_deleted 列）
    remaining = _count("task_item_records", "task_id", task_id)
    assert remaining == 0, (
        f"任务明细仍有 {remaining} 条残留 —— 该表无 is_deleted 列，是永久孤儿"
    )
