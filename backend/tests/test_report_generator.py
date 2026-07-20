from types import SimpleNamespace

from app.services.report_generator import AuditReportGenerator


def test_report_without_leader_decision_stays_a_draft():
    text = AuditReportGenerator._conclusion_text(
        {"report": None, "nonconformities": []}
    )

    assert "尚未由审核组长确认" in text
    assert "不构成认证推荐意见" in text


def test_open_nonconformity_prevents_recommendation():
    text = AuditReportGenerator._conclusion_text(
        {
            "report": SimpleNamespace(
                conclusion="recommend",
                conclusion_notes="建议发证",
            ),
            "nonconformities": [
                SimpleNamespace(severity="minor", status="open")
            ],
        }
    )

    assert "不得形成推荐认证结论" in text
    assert "建议推荐认证" not in text


def test_closed_nonconformity_allows_confirmed_leader_decision():
    text = AuditReportGenerator._conclusion_text(
        {
            "report": SimpleNamespace(
                conclusion="recommend",
                conclusion_notes="整改验证完成",
            ),
            "nonconformities": [
                SimpleNamespace(severity="minor", status="closed")
            ],
        }
    )

    assert "建议推荐认证" in text
    assert "整改验证完成" in text
