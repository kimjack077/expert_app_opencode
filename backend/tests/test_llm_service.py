from app.services.llm_service import LLMService


def test_final_judgment_is_fail_when_any_item_fails():
    service = object.__new__(LLMService)

    result = service._apply_final_judgment_rules(
        {"result": "partial_pass", "remarks": "模型给出了错误判定"},
        fail_count=1,
    )

    assert result == {
        "result": "fail",
        "remarks": "模型给出了错误判定",
    }


def test_final_judgment_keeps_model_result_when_no_item_fails():
    service = object.__new__(LLMService)

    result = service._apply_final_judgment_rules(
        {"result": "partial_pass", "remarks": "存在轻微风险"},
        fail_count=0,
    )

    assert result["result"] == "partial_pass"
