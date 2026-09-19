"""Regression coverage for confirmed defects from the 2026-09-19 EFIS report."""

from types import SimpleNamespace

from app.schemas.enterprise import (
    ProductCreate,
    QualificationCreate,
    RectificationReviewRequest,
)
from app.utils.security import _token_revoked, create_access_token, decode_token


def test_nested_enterprise_create_schemas_do_not_require_path_id():
    assert QualificationCreate(qual_type="体系认证").enterprise_id is None
    assert ProductCreate(name="产品").enterprise_id is None


def test_rectification_review_accepts_json_shape():
    request = RectificationReviewRequest.model_validate(
        {"status": "approved", "rectification_result": "验证通过"}
    )
    assert request.status == "approved"
    assert request.rectification_result == "验证通过"


def test_logout_revokes_only_the_current_session():
    token = create_access_token({"sub": "expert", "sid": "session-a", "rv": None})
    payload = decode_token(token)
    user = SimpleNamespace(revoked_sessions=["session-b"], token_revoked_at=None)

    assert not _token_revoked(payload, user)
    user.revoked_sessions.append("session-a")
    assert _token_revoked(payload, user)
