"""接口层测试：角色权限矩阵 + 记录访问授权一致性。

═══════════════════════════════════════════════════════════════════════════
 这个文件守住什么
═══════════════════════════════════════════════════════════════════════════
角色只有四个（``super_admin`` / ``admin`` / ``expert`` / ``auditor``），
但项目里曾经在 13 个端点各写一遍判断，写的是
``role not in ("admin", "super_admin")``，而**列表接口**用的是
``RECORD_VIEW_ALL_ROLES``（含 ``auditor``）。结果是：

    **审核员能在列表里看到记录，点进去却收到 403。**

用户看到的现象是"系统报错、看不明白"，根因是同一语义的两处实现漂移。
本文件把这个矩阵钉死：列表能看到的，详情必须也能看到；只读角色不得写入。

═══════════════════════════════════════════════════════════════════════════
 运行前提
═══════════════════════════════════════════════════════════════════════════
需先把 ``EFIS_TEST_DB_NAME`` 指向独立测试库（见 conftest.py）。
未配置时全部自动 skip —— 本地与生产共用同一个远程库，裸跑会写脏生产数据。

    set EFIS_TEST_DB_NAME=db_expert_test
    .venv\\Scripts\\python.exe -m pytest tests/test_api_permission_matrix.py -v
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.api

ROLES = ("super_admin", "admin", "expert", "auditor")

# 只读复核角色：可读全量、不可写
READ_ONLY_ROLES = frozenset({"auditor"})
# 管理角色：读写全量
ADMIN_ROLES = frozenset({"super_admin", "admin"})

TEST_PASSWORD = "E2ePerm#2026"

# 角色账号 ID 缓存（由 role_headers 夹具填充），供越权用例比对记录归属。
_ROLE_IDS: dict[str, str] = {}


def _data(resp):
    assert resp.status_code in (200, 201), f"HTTP {resp.status_code}: {resp.text[:400]}"
    payload = resp.json()
    assert payload.get("code") in (0, 200, "0", "200", None), f"业务码异常: {payload}"
    return payload.get("data")


def _login(client, username: str) -> dict:
    resp = client.post(
        "/api/auth/login", json={"username": username, "password": TEST_PASSWORD}
    )
    if resp.status_code != 200:
        pytest.skip(f"角色账号 {username} 无法登录：HTTP {resp.status_code} {resp.text[:200]}")
    token = (resp.json().get("data") or {}).get("access_token")
    if not token:
        pytest.skip(f"登录响应未返回 access_token：{resp.text[:200]}")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def role_headers(client, auth_headers):
    """为四个角色各建一个临时账号并登录，返回 ``{role: headers}``。

    模块级 fixture 自行 teardown（不复用 ``cleanup_registry``，那是用例级）。
    清理时复用 session 级 ``client`` —— 新建 TestClient 会触发事件循环冲突。

    账号 ID 记录在模块级 ``_ROLE_IDS``，供越权用例比对记录归属。
    """
    created: list[str] = []
    sessions: dict[str, dict] = {}

    for role in ROLES:
        username = f"e2e_perm_{role}_{uuid.uuid4().hex[:6]}"
        resp = client.post(
            "/api/users",
            json={
                "username": username,
                "password": TEST_PASSWORD,
                "full_name": f"E2E权限_{role}",
                "role": role,
                "is_active": True,
            },
            headers=auth_headers,
        )
        if resp.status_code not in (200, 201):
            pytest.skip(f"无法创建 {role} 账号：HTTP {resp.status_code} {resp.text[:200]}")
        user_id = _data(resp)["id"]
        created.append(user_id)
        _ROLE_IDS[role] = str(user_id)
        sessions[role] = _login(client, username)

    yield sessions

    for user_id in created:
        try:
            client.delete(f"/api/users/{user_id}", headers=auth_headers)
        except Exception:  # noqa: BLE001 — 清理失败不应让用例报错
            pass


@pytest.fixture(scope="module")
def role_user_ids(role_headers) -> dict[str, str]:
    """``{role: 账号 ID}`` —— 依赖 role_headers 以保证账号已创建。"""
    return dict(_ROLE_IDS)


@pytest.fixture(scope="module")
def probe_record(client, auth_headers, role_headers):
    """取一条真实检查记录用于详情级权限探测。

    优先取「不属于任何测试角色」的记录；取不到就跳过依赖它的用例。
    """
    listed = _data(
        client.get("/api/records", params={"page_size": 50}, headers=auth_headers)
    )
    rows = listed.get("items") if isinstance(listed, dict) else listed
    if not rows:
        pytest.skip("测试库中没有检查记录，无法验证详情级权限")
    record = rows[0]
    return {"id": record["id"], "inspector_id": str(record.get("inspector_id") or "")}


# ---------------------------------------------------------------------------
# 1. 账号管理：仅管理角色可访问
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", ROLES)
def test_user_management_requires_admin_role(client, role_headers, role):
    """/api/users 全系列仅管理员可访问；expert / auditor 必须 403。"""
    headers = role_headers[role]
    resp = client.get("/api/users", headers=headers)

    if role in ADMIN_ROLES:
        assert resp.status_code == 200, f"{role} 应可读取用户列表：{resp.text[:200]}"
    else:
        assert resp.status_code == 403, (
            f"{role} 不应访问用户管理，实际 HTTP {resp.status_code} —— 存在越权风险"
        )


@pytest.mark.parametrize("role", sorted(READ_ONLY_ROLES | {"expert"}))
def test_non_admin_cannot_create_user(client, role_headers, role):
    """非管理角色创建用户必须 403。"""
    resp = client.post(
        "/api/users",
        json={
            "username": f"e2e_should_fail_{uuid.uuid4().hex[:6]}",
            "password": TEST_PASSWORD,
            "role": "expert",
        },
        headers=role_headers[role],
    )
    assert resp.status_code == 403, (
        f"{role} 不应能创建用户，实际 HTTP {resp.status_code}：{resp.text[:200]}"
    )


# ---------------------------------------------------------------------------
# 2. 记录访问授权：列表与详情必须同口径
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", ROLES)
def test_list_visible_implies_detail_visible(client, role_headers, probe_record, role):
    """**核心回归**：列表里能看到的记录，详情接口必须也能打开。

    这正是修复前的缺陷 —— auditor 在列表看到记录，点进详情得到 403。
    """
    headers = role_headers[role]
    listed = client.get("/api/records", params={"page_size": 50}, headers=headers)
    assert listed.status_code == 200, f"{role} 无法读取记录列表：{listed.text[:200]}"

    rows = _data(listed)
    rows = rows.get("items") if isinstance(rows, dict) else rows
    if not rows:
        # expert 是"只看自己"的角色，新建账号名下没有记录时列表本就为空，
        # 此时本断言无从验证。这不是缺陷，但不能就此放过 —— 越权方向由
        # test_field_role_cannot_open_others_record 单独覆盖。
        pytest.skip(f"{role} 的记录列表为空（该角色仅可见本人记录），本断言无从验证")

    target = rows[0]["id"]
    detail = client.get(f"/api/records/{target}", headers=headers)
    assert detail.status_code == 200, (
        f"{role} 在列表中能看到记录 {target}，详情却返回 HTTP {detail.status_code}。"
        "列表级与详情级的授权口径必须一致。"
    )


@pytest.mark.parametrize("role", sorted(READ_ONLY_ROLES))
def test_read_only_role_cannot_write_record(client, role_headers, probe_record, role):
    """只读复核角色可读全量，但不得执行写操作。"""
    headers = role_headers[role]
    record_id = probe_record["id"]

    resp = client.put(
        f"/api/records/{record_id}", json={"remarks": "E2E_只读角色不应写入"}, headers=headers
    )
    assert resp.status_code in (403, 404), (
        f"{role} 不应能修改检查记录，实际 HTTP {resp.status_code}：{resp.text[:200]}"
    )

    submit = client.post(f"/api/records/{record_id}/submit", headers=headers)
    assert submit.status_code in (403, 404, 409), (
        f"{role} 不应能提交检查记录，实际 HTTP {submit.status_code}：{submit.text[:200]}"
    )


@pytest.mark.parametrize("role", ROLES)
def test_report_endpoint_follows_record_permission(client, role_headers, probe_record, role):
    """报告接口的权限必须与记录详情一致 —— 不允许"详情打不开但报告能下"。"""
    headers = role_headers[role]
    detail = client.get(f"/api/records/{probe_record['id']}", headers=headers)
    report = client.get(f"/api/records/{probe_record['id']}/report", headers=headers)

    if detail.status_code == 200:
        assert report.status_code == 200, (
            f"{role} 能打开详情却打不开报告：HTTP {report.status_code} —— 权限口径不一致"
        )
    else:
        assert report.status_code in (403, 404), (
            f"{role} 打不开详情（HTTP {detail.status_code}）却能访问报告"
            f"（HTTP {report.status_code}）—— 存在越权读取风险"
        )


# ---------------------------------------------------------------------------
# 3. 越权方向：现场角色不得读取他人记录
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["expert"])
def test_field_role_cannot_open_others_record(
    client, role_headers, role_user_ids, probe_record, role
):
    """现场执行角色只能看自己的记录 —— 打开他人记录必须 403/404。

    这是「列表可见 ⇒ 详情可见」的**反向断言**：授权放宽时必须仍然收紧另一端。
    修复详情级权限时最容易犯的错，就是把 ``can_view_all_records`` 用在了
    所有角色上，于是每个检查员都能读到全公司的记录。
    """
    headers = role_headers[role]
    if probe_record["inspector_id"] == role_user_ids.get(role):
        pytest.skip("探测记录恰好属于该角色，无法验证越权方向")

    detail = client.get(f"/api/records/{probe_record['id']}", headers=headers)
    assert detail.status_code in (403, 404), (
        f"{role} 不应能打开他人记录 {probe_record['id']}，"
        f"实际 HTTP {detail.status_code} —— 存在越权读取风险"
    )

    report = client.get(f"/api/records/{probe_record['id']}/report", headers=headers)
    assert report.status_code in (403, 404), (
        f"{role} 不应能下载他人记录的报告，实际 HTTP {report.status_code}"
    )


# ---------------------------------------------------------------------------
# 4. 未鉴权一律拒绝
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/api/records",
        "/api/templates",
        "/api/enterprises",
        "/api/tasks",
        "/api/users",
        "/api/industries",
        "/api/analytics/dashboard",
    ],
)
def test_anonymous_is_rejected(client, path):
    """未带 token 必须 401/403 —— 任何 200 都意味着数据泄漏。"""
    resp = client.get(path)
    assert resp.status_code in (401, 403), (
        f"{path} 未鉴权却返回 HTTP {resp.status_code} —— 存在越权风险"
    )


def test_invalid_token_is_rejected(client):
    """伪造/过期 token 必须被拒，不能降级为匿名可读。"""
    bad = {"Authorization": "Bearer not-a-real-token"}
    for path in ("/api/records", "/api/users", "/api/enterprises"):
        resp = client.get(path, headers=bad)
        assert resp.status_code in (401, 403), (
            f"{path} 使用伪造 token 返回 HTTP {resp.status_code}"
        )
