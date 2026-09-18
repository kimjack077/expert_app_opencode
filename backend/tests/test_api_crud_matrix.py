"""接口层测试：CRUD 全矩阵 + 数据准确性 + 一致性。

对应测试需求的第 1、2 项：
  1. 数据录入与处理无误 —— 往返一致性、边界与类型校验、主数据关联完整性
  2. 增删改查完整可用 —— C/R/U/D 全链路、软删除、幂等性、权限矩阵

═══════════════════════════════════════════════════════════════════════════
 运行前提
═══════════════════════════════════════════════════════════════════════════
必须先把 ``EFIS_TEST_DATABASE_URL`` 指向**独立测试库**（见 conftest.py 顶部）。
未配置时本文件所有用例自动 skip，这是有意的保护——
本地与生产共用同一个远程库（db_expert_claude），裸跑会写脏生产数据。

    # 一次性：CREATE DATABASE db_expert_test TEMPLATE db_expert_claude;
    set EFIS_TEST_DATABASE_URL=postgresql+asyncpg://user:pwd@49.232.213.79:5432/db_expert_test
    .venv\\Scripts\\python.exe -m pytest tests/test_api_crud_matrix.py -v
"""

from __future__ import annotations

import json
import uuid

import pytest

pytestmark = pytest.mark.api


# ---------------------------------------------------------------------------
# 实体规格表 —— 新增实体只需在此登记一行
# ---------------------------------------------------------------------------
# 说明：``create`` 返回最小可用载荷；``patch`` 用于验证「改」是否真正落库。
# 若某实体的必填字段调整，只需改这里一处。

ENTITY_SPECS = {
    "enterprise": {
        "list_path": "/api/enterprises",
        "create": lambda s: {"name": f"E2E_TEST_企业_{s}", "risk_level": "B"},
        "patch": lambda s: {"contact_person": "E2E联系人", "contact_phone": "13800000000"},
        "expect_patched": lambda d: d.get("contact_person") == "E2E联系人",
        "id_key": "id",
        "detail_404_after_delete": True,
    },
    "template": {
        "list_path": "/api/templates",
        "create": lambda s: {
            "name": f"E2E_TEST_模板_{s}",
            "code": f"E2E_{s}",
            "description": "自动化测试模板",
        },
        "patch": lambda s: {"description": "已修改的说明"},
        "expect_patched": lambda d: d.get("description") == "已修改的说明",
        "id_key": "id",
        # ⚠️ 已软删模板对管理员仍可只读访问（templates.py:244，为历史任务回放有意保留），
        #    因此不断言详情 404；但仍必须从列表中消失。
        #    注：这会造成"列表看不到、直接开 URL 却能看到"的观感不一致，已记入方案文档待决项。
        "detail_404_after_delete": False,
    },
    "task": {
        "list_path": "/api/tasks",
        "create": lambda s: {"title": f"E2E_TEST_任务_{s}", "target_name": "E2E测试对象"},
        "patch": lambda s: {"title": f"E2E_TEST_任务_{s}_已改"},
        "expect_patched": lambda d: d.get("title", "").endswith("_已改"),
        "id_key": "id",
        "detail_404_after_delete": True,
    },
    "industry": {
        "list_path": "/api/industries",
        "create": lambda s: {
            "name": f"E2E_TEST_行业_{s}",
            "code": f"E2EIND_{s}",
            "description": "自动化测试行业分类",
            "sort_order": 0,
        },
        "patch": lambda s: {"description": "已修改的行业说明"},
        "expect_patched": lambda d: d.get("description") == "已修改的行业说明",
        "id_key": "id",
        # 行业分类被企业/用户引用，删除采用软删；详情是否 404 取决于实现，
        # 这里只强制「不得再出现在列表中」，避免把设计歧义误判为缺陷。
        "detail_404_after_delete": False,
    },
    "audit-project": {
        "list_path": "/api/audit-projects",
        # 审核项目必须挂在真实企业下，企业 ID 由 crud_context 夹具注入
        "create": lambda s: {
            "title": f"E2E_TEST_审核项目_{s}",
            "enterprise_id": _CTX["enterprise_id"],
            "audit_type": "initial",
            "certification_systems": ["Q"],
            "remarks": "自动化测试项目",
        },
        "patch": lambda s: {"remarks": "已修改的项目备注"},
        "expect_patched": lambda d: d.get("remarks") == "已修改的项目备注",
        "id_key": "id",
        "detail_404_after_delete": True,
    },
}

# 需要外部主数据的实体，从该上下文取（由 crud_context 夹具填充）。
# 之所以用模块级字典而不是改 create 的签名：现有 5 个实体的 lambda 都只吃
# 一个 suffix 参数，改签名会波及全部；这里用最小改动接入新实体。
_CTX: dict[str, str] = {}


@pytest.fixture(scope="session")
def crud_context(shared_enterprise_id):
    """为需要外部主数据的实体准备上下文（当前只有审核项目需要企业 ID）。"""
    _CTX.setdefault("enterprise_id", shared_enterprise_id)
    return _CTX


def _data(resp):
    """解开统一响应体 ``{code, message, data, timestamp}``。"""
    assert resp.status_code in (200, 201), f"HTTP {resp.status_code}: {resp.text[:400]}"
    payload = resp.json()
    assert payload.get("code") in (0, 200, "0", "200", None), f"业务码异常: {payload}"
    return payload.get("data")


def _detail_path(list_path: str, ident: str) -> str:
    return f"{list_path}/{ident}"


def _stable_body(resp) -> str:
    """归一化响应体，剔除每次都变的 ``timestamp`` 字段后再比较。

    统一响应体形如 ``{code, message, data, timestamp}``，其中 timestamp 是
    请求时刻，天然每次不同——直接逐字节比对会误报。
    """
    try:
        payload = resp.json()
    except Exception:  # noqa: BLE001 — 非 JSON 响应原样返回
        return resp.text
    payload.pop("timestamp", None)
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 1. CRUD 全生命周期
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entity", sorted(ENTITY_SPECS))
def test_crud_lifecycle(
    client, auth_headers, entity, unique_suffix, cleanup_registry, crud_context
):
    """C → R → U → D → R(应 404)：一次跑完整条增删改查链路。"""
    spec = ENTITY_SPECS[entity]
    list_path = spec["list_path"]

    if entity == "audit-project" and "enterprise_id" not in crud_context:
        pytest.skip("测试库中没有企业数据，无法创建审核项目")

    # --- C：创建 ---
    resp = client.post(list_path, json=spec["create"](unique_suffix), headers=auth_headers)
    created = _data(resp)
    assert created, f"{entity} 创建未返回数据体"
    ident = created.get(spec["id_key"]) or created.get("id")
    assert ident, f"{entity} 创建后未返回主键：{created}"
    cleanup_registry.append((list_path.rsplit("/", 1)[-1], ident))

    # --- R：读取详情，且必须能在列表中检索到 ---
    resp = client.get(_detail_path(list_path, ident), headers=auth_headers)
    detail = _data(resp)
    assert detail, f"{entity} 详情为空"

    resp = client.get(list_path, params={"keyword": unique_suffix, "page_size": 100}, headers=auth_headers)
    listed = _data(resp)
    items = listed.get("items") if isinstance(listed, dict) else listed
    items = items or []
    assert any(str(it.get("id")) == str(ident) for it in items), (
        f"{entity} 创建成功但列表中检索不到（列表/详情口径不一致）"
    )

    # --- U：修改并回读校验 ---
    patch_payload = spec["patch"](unique_suffix)
    resp = client.put(_detail_path(list_path, ident), json=patch_payload, headers=auth_headers)
    _data(resp)

    resp = client.get(_detail_path(list_path, ident), headers=auth_headers)
    after = _data(resp)
    assert spec["expect_patched"](after), (
        f"{entity} 修改未生效。提交 {patch_payload}，回读得到 {after}"
    )

    # --- D：删除 ---
    resp = client.delete(_detail_path(list_path, ident), headers=auth_headers)
    assert resp.status_code in (200, 204), f"{entity} 删除失败：{resp.status_code}"

    # --- R：删除后不得再出现在列表 ---
    if spec.get("detail_404_after_delete", True):
        resp = client.get(_detail_path(list_path, ident), headers=auth_headers)
        assert resp.status_code == 404, (
            f"{entity} 删除后详情仍可访问（HTTP {resp.status_code}）——软删除过滤缺失"
        )

    resp = client.get(list_path, params={"keyword": unique_suffix, "page_size": 100}, headers=auth_headers)
    listed = _data(resp)
    items = (listed.get("items") if isinstance(listed, dict) else listed) or []
    assert not any(str(it.get("id")) == str(ident) for it in items), (
        f"{entity} 删除后仍出现在列表中——列表接口漏加 is_deleted 过滤"
    )


# ---------------------------------------------------------------------------
# 2. 数据录入准确性：往返一致性
# ---------------------------------------------------------------------------


def test_roundtrip_field_fidelity(client, auth_headers, unique_suffix, cleanup_registry):
    """写入的每个字段必须原样读回——这是"数据录入无误"的第一道防线。"""
    suffix = unique_suffix
    payload = {
        "name": f"E2E_TEST_往返_{suffix}",
        "credit_code": f"9137{suffix}",
        "address": "山东省济南市历下区测试路 1 号",
        "legal_person": "张三",
        "contact_person": "李四",
        "contact_phone": "13900000001",
        "risk_level": "C",
        "remarks": "含中文、空格与特殊符号 <>\"'&",
    }

    created = _data(client.post("/api/enterprises", json=payload, headers=auth_headers))
    ident = created["id"]
    cleanup_registry.append(("enterprises", ident))

    detail = _data(client.get(f"/api/enterprises/{ident}", headers=auth_headers))

    for field, expected in payload.items():
        assert detail.get(field) == expected, (
            f"字段 {field} 往返不一致：写入 {expected!r}，读回 {detail.get(field)!r}"
        )


@pytest.mark.parametrize(
    "payload,reason",
    [
        ({"name": ""}, "空名称应被拒绝"),
        ({"name": "x" * 201}, "超长名称应被拒绝"),
        ({"name": "E2E_非法枚举", "risk_level": "Z"}, "非法风险等级应被拒绝"),
        ({"name": "E2E_非法类型", "employee_count": -1}, "负数员工数应被拒绝"),
        ({}, "缺少必填字段应被拒绝"),
    ],
)
def test_create_rejects_invalid_payload(client, auth_headers, payload, reason):
    """边界与类型校验：非法输入必须被 4xx 拒绝，不得落库。"""
    resp = client.post("/api/enterprises", json=payload, headers=auth_headers)
    assert 400 <= resp.status_code < 500, (
        f"{reason}，实际返回 HTTP {resp.status_code}：{resp.text[:300]}"
    )


# ---------------------------------------------------------------------------
# 3. 幂等性 —— GET 不得有写副作用
# ---------------------------------------------------------------------------


def test_get_endpoints_have_no_write_side_effects(client, auth_headers, unique_suffix, cleanup_registry):
    """连续 GET 同一资源，结果必须逐字节稳定。

    回归目标：``GET /tasks/{id}/records`` 曾内部执行 delete + insert + commit，
    导致「任何一次查看都会改动生产数据」，并发时还会重复插入。
    """
    task = _data(
        client.post(
            "/api/tasks",
            json={"title": f"E2E_TEST_幂等_{unique_suffix}", "target_name": "E2E幂等对象"},
            headers=auth_headers,
        )
    )
    task_id = task["id"]
    cleanup_registry.append(("tasks", task_id))

    reads = [client.get(f"/api/tasks/{task_id}/records", headers=auth_headers) for _ in range(3)]

    bodies = [_stable_body(r) for r in reads]
    assert len(set(bodies)) == 1, (
        "连续 3 次 GET 返回了不同的业务数据——查询接口存在写副作用或非确定性输出。\n"
        f"首次：{bodies[0][:300]}\n末次：{bodies[-1][:300]}"
    )


# ---------------------------------------------------------------------------
# 4. 软删除级联 —— 防止"任务列表指向已删项目"
# ---------------------------------------------------------------------------


def test_soft_deleted_project_tasks_are_not_listed(client, auth_headers, unique_suffix):
    """项目软删除后，其任务不得再出现在「我的审核任务」。

    回归目标：外部测试 P0-29 —— ``my-tasks`` 只过滤了 plan_item.is_deleted，
    未过滤 project.is_deleted，导致点击任务必定 404。
    """
    # 审核项目必须挂真实企业（enterprise_id 为必填 UUID）
    ents = _data(client.get("/api/enterprises", params={"page_size": 1}, headers=auth_headers))
    ent_items = (ents.get("items") if isinstance(ents, dict) else ents) or []
    if not ent_items:
        pytest.skip("测试库中没有企业，无法创建审核项目")
    enterprise_id = ent_items[0]["id"]

    project = _data(
        client.post(
            "/api/audit-projects",
            json={
                "title": f"E2E_TEST_项目_{unique_suffix}",
                "enterprise_id": enterprise_id,
                "audit_type": "initial",
                "audit_days": 1.0,
            },
            headers=auth_headers,
        )
    )
    project_id = project["id"]

    before = _data(client.get("/api/audit-projects/my-tasks", headers=auth_headers)) or []
    before_items = before.get("items") if isinstance(before, dict) else before
    before_ids = {str(it.get("project_id")) for it in (before_items or [])}

    client.delete(f"/api/audit-projects/{project_id}", headers=auth_headers)

    after = _data(client.get("/api/audit-projects/my-tasks", headers=auth_headers)) or []
    after_items = after.get("items") if isinstance(after, dict) else after
    after_ids = {str(it.get("project_id")) for it in (after_items or [])}

    assert project_id not in after_ids, (
        f"项目 {project_id} 已软删除，其任务仍出现在 my-tasks 中——"
        "列表过滤缺失（这正是外部测试报 404 的根因）"
    )
    assert after_ids <= before_ids, "my-tasks 在删除项目后反而多出了条目"


# ---------------------------------------------------------------------------
# 5. 权限矩阵
# ---------------------------------------------------------------------------


def test_anonymous_requests_are_rejected(client):
    """未带 token 的请求必须 401/403，不得泄漏数据。"""
    for path in ("/api/enterprises", "/api/templates", "/api/tasks", "/api/records"):
        resp = client.get(path)
        assert resp.status_code in (401, 403), (
            f"{path} 未鉴权却返回 HTTP {resp.status_code} —— 存在越权风险"
        )
