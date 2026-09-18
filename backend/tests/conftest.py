"""EFIS 后端测试公共夹具。

═══════════════════════════════════════════════════════════════════════════
 安全前置（最重要的一条）
═══════════════════════════════════════════════════════════════════════════
本仓库的本地开发环境与线上生产**共用同一个远程 PostgreSQL**
（``PG_HOST=49.232.213.79`` / ``PG_DB=db_expert_claude``）。
这意味着：任何"随手跑一下"的测试都会直接写脏生产数据。

因此本文件强制两条规则：

1. 需要数据库的测试**只在**配置了独立测试库时运行（``EFIS_TEST_DB_NAME``）；
   未配置时自动 skip，绝不回退到 ``backend/.env`` 里的生产连接。
2. 若配置指向生产主机或生产库名，**直接抛错拒绝启动**。

用法::

    # 一次性创建测试库（已完成：db_expert_test，47 表 / 760 列，与生产同构）
    #   CREATE DATABASE db_expert_test TEMPLATE db_expert_claude;
    set EFIS_TEST_DB_NAME=db_expert_test
    cd backend && .venv\\Scripts\\python.exe -m pytest tests/ -v

只跑不需要数据库的层（安全，随时可跑）::

    .venv\\Scripts\\python.exe -m pytest tests/ -v -m "contract or unit"
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

# ---------------------------------------------------------------------------
# 0. 生产库保护 —— 必须在任何 app.* 模块被导入之前完成
# ---------------------------------------------------------------------------

TEST_DB_NAME_ENV = "EFIS_TEST_DB_NAME"
TEST_DB_URL_ENV = "EFIS_TEST_DATABASE_URL"

# 生产库指纹：命中任意一项即拒绝运行
PRODUCTION_HOSTS = frozenset({"49.232.213.79"})
PRODUCTION_DB_NAMES = frozenset({"db_expert_claude", "postgres"})


def _apply_test_db_env() -> str | None:
    """解析测试库配置，并把结果写入 ``PG_*`` 环境变量供 app.config 读取。

    支持两种配置方式，**推荐方式一**：

    方式一（推荐）—— 只覆盖库名，其余连接参数沿用 ``backend/.env``::

        set EFIS_TEST_DB_NAME=db_expert_test

    方式二 —— 完整连接串（注意：密码中的 ``@`` ``:`` ``/`` 等需 URL 编码）::

        set EFIS_TEST_DATABASE_URL=postgresql+asyncpg://user:p%40ss@host:5432/db_expert_test

    返回被测库名；未配置时返回 ``None``。
    """
    # --- 方式一：只指定库名 ---
    db_name = (os.environ.get(TEST_DB_NAME_ENV) or "").strip()
    if db_name:
        if db_name in PRODUCTION_DB_NAMES:
            raise RuntimeError(
                f"\n[EFIS 测试安全闸] 拒绝启动：{TEST_DB_NAME_ENV}={db_name} "
                "指向生产库。自动化测试绝不允许写生产数据。\n"
            )
        os.environ["PG_DB"] = db_name
        return db_name

    # --- 方式二：完整连接串 ---
    raw = (os.environ.get(TEST_DB_URL_ENV) or "").strip()
    if not raw:
        return None

    parsed = urlparse(raw)
    host = parsed.hostname or ""
    db_name = (parsed.path or "").lstrip("/")

    if host in PRODUCTION_HOSTS or db_name in PRODUCTION_DB_NAMES:
        raise RuntimeError(
            f"\n[EFIS 测试安全闸] 拒绝启动：{TEST_DB_URL_ENV} 指向生产库 "
            f"({host}/{db_name})。\n"
            "自动化测试绝不允许写生产数据。请改用独立测试库，例如：\n"
            "  CREATE DATABASE db_expert_test TEMPLATE db_expert_claude;\n"
            f"  {TEST_DB_NAME_ENV}=db_expert_test        # 推荐：只覆盖库名\n"
        )

    if parsed.username:
        os.environ["PG_USER"] = parsed.username
    if parsed.password:
        os.environ["PG_PASSWORD"] = parsed.password
    if host:
        os.environ["PG_HOST"] = host
    if parsed.port:
        os.environ["PG_PORT"] = str(parsed.port)
    if db_name:
        os.environ["PG_DB"] = db_name

    return db_name


TEST_DB_NAME = _apply_test_db_env()

# 让 `import app.*` 在 backend/ 目录下直接可用
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ---------------------------------------------------------------------------
# 1. skip 开关
# ---------------------------------------------------------------------------

requires_test_db = pytest.mark.skipif(
    not TEST_DB_NAME,
    reason=(
        f"未配置测试库（{TEST_DB_NAME_ENV}），跳过需要数据库的用例。"
        "（这是有意的保护：避免误写生产库 db_expert_claude）"
    ),
)


def pytest_collection_modifyitems(config, items):
    """未配置测试库时，自动给 api/report 用例打上 skip。"""
    if TEST_DB_NAME:
        return
    skip_marker = pytest.mark.skip(
        reason=f"未配置测试库（{TEST_DB_NAME_ENV}），跳过需要数据库的用例"
    )
    for item in items:
        if item.get_closest_marker("api") or item.get_closest_marker("report"):
            item.add_marker(skip_marker)


def pytest_report_header(config):
    if TEST_DB_NAME:
        host = os.environ.get("PG_HOST")
        if not host:
            try:
                from app.config import settings

                host = settings.PG_HOST
            except Exception:  # noqa: BLE001
                host = "<未解析>"
        return f"EFIS 测试库：{host}/{TEST_DB_NAME}（隔离库，安全）"
    return (
        "EFIS 测试库：未配置 —— 仅运行 contract/unit 层；"
        f"设置 {TEST_DB_NAME_ENV}=db_expert_test 后可运行 api/report 层"
    )


# ---------------------------------------------------------------------------
# 2. 数据库夹具
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def db_engine():
    """会话级数据库引擎（仅当测试库已配置时可用）。"""
    if not TEST_DB_NAME:
        pytest.skip("未配置测试库")

    from sqlalchemy.ext.asyncio import create_async_engine

    from app.config import settings

    engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=None)
    yield engine


@pytest.fixture(scope="session")
def client(db_engine):
    """FastAPI TestClient（走 ASGI，无需起服务）。

    注意：TestClient 会触发 app lifespan，因此依赖 db_engine 已确认指向测试库。
    """
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client) -> str:
    """管理员 token。凭据可由环境变量覆盖。"""
    username = os.environ.get("EFIS_TEST_ADMIN_USER", "admin")
    password = os.environ.get("EFIS_TEST_ADMIN_PASSWORD", "admin123")

    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    if resp.status_code != 200:
        pytest.skip(f"测试库缺少可用管理员账号（{username}），跳过依赖鉴权的用例")

    payload = resp.json()
    data = payload.get("data") or {}
    token = data.get("access_token") or data.get("token")
    if not token:
        pytest.skip("登录响应中未取到 access_token")
    return token


@pytest.fixture(scope="session")
def auth_headers(admin_token) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


# ---------------------------------------------------------------------------
# 3. 造数与清理
# ---------------------------------------------------------------------------


@pytest.fixture
def unique_suffix() -> str:
    """用例级唯一后缀，避免测试数据互相干扰。"""
    import uuid

    return uuid.uuid4().hex[:8]


@pytest.fixture(scope="session")
def shared_enterprise_id(client, auth_headers) -> str:
    """测试库中一条可用企业的 ID（会话级缓存）。

    多个测试文件都需要「把检查记录挂到真实企业下」。远程库（49.232.213.79）
    每次往返都有真实延迟，重复查询纯属浪费。取不到则 skip 依赖它的用例。
    """
    resp = client.get(
        "/api/enterprises", params={"page_size": 1}, headers=auth_headers
    )
    if resp.status_code != 200:
        pytest.skip(f"无法读取企业列表：HTTP {resp.status_code}")
    data = resp.json().get("data")
    rows = data.get("items") if isinstance(data, dict) else data
    if not rows:
        pytest.skip("测试库中没有企业数据")
    return rows[0]["id"]


@pytest.fixture
def cleanup_registry(client, auth_headers):
    """登记"测试结束后需要删除"的资源，teardown 时逆序清理。

    用例中这样用::

        def test_x(client, auth_headers, cleanup_registry):
            rid = create_record(...)
            cleanup_registry.append(("records", rid))

    ⚠️ 必须复用 session 级的 ``client``，**不要**在 teardown 里新建 TestClient——
    新建会创建新的事件循环，而 asyncpg 连接池绑定在旧循环上，触发
    ``RuntimeError: got Future attached to a different loop``，表现为随机的
    连接失败与 InternalClientError。
    """
    registry: list[tuple[str, str]] = []
    yield registry

    if not TEST_DB_NAME:
        return

    path_map = {
        "records": "/api/records/{id}",
        "templates": "/api/templates/{id}",
        "tasks": "/api/tasks/{id}",
        "enterprises": "/api/enterprises/{id}",
        "audit-projects": "/api/audit-projects/{id}",
    }
    for kind, ident in reversed(registry):
        template = path_map.get(kind)
        if not template:
            continue
        try:
            client.delete(template.format(id=ident), headers=auth_headers)
        except Exception:  # noqa: BLE001 — 清理失败不应让用例报错
            pass
