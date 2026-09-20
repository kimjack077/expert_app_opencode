"""2026-09-20 六缺陷修复的回归用例（F1 导出鉴权 / F4 响应体 / F5 Pydantic v2 / F6 事件循环）。

背景：2026-09-20 一轮修复了 6 项缺陷（F1~F6），但只在文档里列了用例编号
（``docs/EFIS_全功能测试用例_2026-09-20.md``），**没有落成可执行的用例**。
按项目约定「修完 bug 必须补一条回归用例」，本文件把其中最容易被改回去的几条钉死。

覆盖范围与不覆盖的部分：

* **F1 导出鉴权**：断言「无凭据=401、凭据有效=放行到业务层（404/409，绝不是 401）、
  凭据非法=401」。刻意使用**不存在的项目 UUID**，因此断言与库内数据无关，
  不会因演示数据增删而失效。
* **F4 统一响应体**：键集合与 timestamp 格式。
* **F5 Pydantic v2**：禁止 ``class Config`` 回流；``ApiResponse`` 的 timestamp 必须序列化为字符串。
* **F6 事件循环**：同一进程内连续创建多个 ``TestClient``（各自一个事件循环），
  登录不得因 ``Event loop is closed`` 失败。
* **不覆盖** F2/F3（测试库凭据、用户表数据卫生）—— 那两项是**数据/环境**问题
  （根因是测试库落后两个 Alembic 迁移），不属于代码回归，无法用单元用例钉死。
"""
from __future__ import annotations

import pathlib
import re
import uuid

import pytest

TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$")

# 刻意使用不存在的项目，保证断言与库内数据无关
ABSENT_PROJECT = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# F1 导出鉴权：Authorization 头优先，?token= 兼容
# ---------------------------------------------------------------------------

@pytest.mark.api
class TestExportAuthentication:
    """导出端点鉴权优先级与失败语义。

    注意断言的是「**不是 401**」而不是 200/409：
    凭据有效时请求会继续走到项目访问校验，对不存在的项目必然 404；
    若鉴权被绕过或误判，这里会变成 401，用例立刻失败。
    """

    def _url(self, kind: str) -> str:
        return f"/api/audit-projects/{ABSENT_PROJECT}/export/{kind}"

    @pytest.mark.parametrize("kind", ["word", "pdf"])
    def test_missing_credentials_returns_401(self, client, kind):
        resp = client.get(self._url(kind))
        assert resp.status_code == 401, (
            f"{kind} 导出无凭据应 401，实际 {resp.status_code}：{resp.text[:200]}"
        )

    @pytest.mark.parametrize("kind", ["word", "pdf"])
    def test_bearer_header_is_accepted(self, client, auth_headers, kind):
        resp = client.get(self._url(kind), headers=auth_headers)
        assert resp.status_code != 401, (
            f"{kind} 导出带 Bearer 头不应被判未认证，实际 {resp.status_code}"
        )

    @pytest.mark.parametrize("kind", ["word", "pdf"])
    def test_query_token_still_accepted(self, client, admin_token, kind):
        """旧版 ?token= 通道必须继续可用（前端切换期间不能断）。"""
        resp = client.get(self._url(kind), params={"token": admin_token})
        assert resp.status_code != 401, (
            f"{kind} 导出的 ?token= 兼容通道失效，实际 {resp.status_code}"
        )

    def test_garbage_bearer_token_returns_401(self, client):
        resp = client.get(
            self._url("word"), headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert resp.status_code == 401

    def test_garbage_query_token_returns_401(self, client):
        resp = client.get(self._url("word"), params={"token": "not-a-real-token"})
        assert resp.status_code == 401

    def test_refresh_token_cannot_be_used_as_access_token(self, client, admin_token):
        """?token= 走 get_user_from_token，必须校验 type=access。"""
        from app.utils.security import create_refresh_token

        refresh = create_refresh_token({"sub": "admin"})
        assert refresh != admin_token
        resp = client.get(self._url("word"), params={"token": refresh})
        assert resp.status_code == 401, "refresh token 不得当作 access token 使用"


# ---------------------------------------------------------------------------
# F4 统一响应体
# ---------------------------------------------------------------------------

@pytest.mark.api
class TestUnifiedResponseEnvelope:
    ENDPOINTS = [
        "/api/auth/me",
        "/api/users",
        "/api/enterprises",
        "/api/industries/tree",
        "/api/templates",
        "/api/records",
        "/api/tasks",
        "/api/analytics/dashboard",
        "/api/knowledge/documents",
        "/api/statistics/overview",
        "/api/audit-projects",
    ]

    @pytest.mark.parametrize("path", ENDPOINTS)
    def test_envelope_keys_and_timestamp(self, client, auth_headers, path):
        resp = client.get(path, headers=auth_headers)
        assert resp.status_code == 200, f"{path} → HTTP {resp.status_code}"
        body = resp.json()
        assert set(body.keys()) == {"code", "message", "data", "timestamp"}, (
            f"{path} 响应键集合漂移：{sorted(body.keys())}"
        )
        assert TS_RE.match(str(body["timestamp"])), (
            f"{path} timestamp 非统一 ISO+00:00 格式：{body['timestamp']!r}"
        )


# ---------------------------------------------------------------------------
# F5 Pydantic v2
# ---------------------------------------------------------------------------

class TestPydanticV2Migration:
    def test_no_legacy_class_config_in_schemas(self):
        """``class Config`` 是 Pydantic v1 写法，v2 下会持续告警并最终失效。"""
        offenders = []
        root = pathlib.Path(__file__).resolve().parents[1] / "app"
        for py in root.rglob("*.py"):
            src = py.read_text(encoding="utf-8")
            if "class Config:" in src:
                offenders.append(str(py.relative_to(root.parent)))
        assert not offenders, f"仍有 Pydantic v1 风格 class Config：{offenders}"

    def test_api_response_timestamp_serializes_to_string(self):
        """原先靠 ``json_encoders`` 转字符串，v2 下已迁移为 field_serializer。"""
        from datetime import datetime, timezone

        from app.schemas.common import ApiResponse

        dumped = ApiResponse(
            code=200, message="success", data=None, timestamp=datetime.now(timezone.utc)
        ).model_dump(mode="json")
        assert isinstance(dumped["timestamp"], str)
        assert TS_RE.match(dumped["timestamp"]), dumped["timestamp"]

    def test_make_response_returns_plain_dict(self):
        """统一响应工具返回 dict，交由 FastAPI 序列化；不再是 ApiResponse 实例。"""
        from app.utils.response import make_response, utc_now_iso

        body = make_response(data={"a": 1})
        assert isinstance(body, dict)
        assert set(body) == {"code", "message", "data", "timestamp"}
        assert TS_RE.match(body["timestamp"])
        assert TS_RE.match(utc_now_iso())


# ---------------------------------------------------------------------------
# F6 跨事件循环
# ---------------------------------------------------------------------------

@pytest.mark.api
class TestEventLoopSafety:
    def test_consecutive_test_clients_do_not_break_login(self):
        """每个 TestClient 自带事件循环；连接池若跨循环复用会抛
        ``RuntimeError: Event loop is closed`` 或 ``got Future attached to a
        different loop``，表现为登录 500。
        """
        from fastapi.testclient import TestClient

        from app.main import app

        codes = []
        for _ in range(3):
            with TestClient(app) as c:
                r = c.post(
                    "/api/auth/login",
                    json={"username": "admin", "password": "admin123"},
                )
                codes.append(r.status_code)
                if r.status_code == 200:
                    token = r.json()["data"]["access_token"]
                    codes.append(
                        c.get(
                            "/api/auth/me",
                            headers={"Authorization": f"Bearer {token}"},
                        ).status_code
                    )
        assert all(code == 200 for code in codes), f"跨事件循环登录失败：{codes}"
