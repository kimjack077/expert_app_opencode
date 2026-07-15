import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from app.services.agent_service import agent_service
from app.services.template_recommendation_service import (
    template_recommendation_service,
)


async def _stream_response(*chunks):
    for chunk in chunks:
        yield chunk


def _chunk(content=None, tool_calls=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content, tool_calls=tool_calls)
            )
        ]
    )


def _tool_call(index, call_id, name, arguments):
    return SimpleNamespace(
        index=index,
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def test_get_enterprise_history_uses_inspection_records():
    enterprise_id = uuid4()
    enterprise = SimpleNamespace(
        id=enterprise_id,
        name="测试企业",
        risk_level="B",
    )
    failed_item = SimpleNamespace(
        item_title="消防通道",
        problem_description="通道被占用",
        rectification_suggestion="立即清理",
        radio_value="fail",
        result=None,
    )
    record = SimpleNamespace(
        id=uuid4(),
        inspection_date=None,
        status="submitted",
        overall_result="fail",
        items=[failed_item],
    )

    db = AsyncMock()
    db.get.return_value = enterprise
    execute_result = Mock()
    execute_result.scalars.return_value.all.return_value = [record]
    db.execute.return_value = execute_result

    result = asyncio.run(
        agent_service._tool_get_enterprise_history(
            {"enterprise_name": enterprise.name},
            {"enterprise_id": str(enterprise_id)},
            db,
        )
    )

    assert result["total_inspections"] == 1
    assert result["history"][0]["issues"] == [
        {
            "title": "消防通道",
            "problem": "通道被占用",
            "rectification": "立即清理",
        }
    ]


def test_recommend_template_accepts_enterprise_name_in_id_argument():
    enterprise_id = uuid4()
    enterprise = SimpleNamespace(id=enterprise_id, name="测试企业")
    db = AsyncMock()
    execute_result = Mock()
    execute_result.scalar_one_or_none.return_value = enterprise
    db.execute.return_value = execute_result

    recommendations = [{"template_id": str(uuid4()), "template_name": "安全检查"}]
    with patch.object(
        template_recommendation_service,
        "recommend_templates",
        AsyncMock(return_value=recommendations),
    ) as recommend_templates:
        result = asyncio.run(
            agent_service._tool_recommend_template(
                {"enterprise_id": enterprise.name},
                {},
                db,
            )
        )

    assert result["enterprise_id"] == str(enterprise_id)
    assert result["recommendations"] == recommendations
    recommend_templates.assert_awaited_once_with(str(enterprise_id), db, top_k=3)


def test_execute_tool_hides_internal_errors_and_rolls_back():
    db = AsyncMock()

    with patch.object(
        agent_service,
        "_tool_recommend_template",
        AsyncMock(side_effect=RuntimeError("sensitive SQL details")),
    ):
        result = asyncio.run(
            agent_service._execute_tool("recommend_template", {}, {}, db)
        )

    assert result == {
        "error": "工具执行失败，请确认对象后重试或换一种说法",
        "retryable": True,
    }
    assert "sensitive SQL details" not in str(result)
    db.rollback.assert_awaited_once()


def test_chat_stream_hides_tool_narration_and_avoids_duplicate_knowledge_searches():
    db = AsyncMock()
    repeated_call = _tool_call(
        0,
        "call-1",
        "search_knowledge_base",
        '{"query":"3.5 追溯系统"}',
    )
    final_chunk = _chunk(content="第3.5条的正式定义。")
    create = AsyncMock(
        side_effect=[
            _stream_response(_chunk("我先检索。", [repeated_call])),
            _stream_response(
                _chunk(
                    "我继续检索。",
                    [
                        _tool_call(
                            0,
                            "call-2",
                            "search_knowledge_base",
                            '{"query":"3.5 追溯系统"}',
                        )
                    ],
                )
            ),
            _stream_response(final_chunk),
        ]
    )

    async def collect_events():
        return [
            event
            async for event in agent_service.chat_stream(
                message="第3.5条怎么定义？",
                context={},
                conversation=[],
                db=db,
            )
        ]

    with (
        patch.object(agent_service, "_build_context", AsyncMock(return_value={})),
        patch.object(
            agent_service,
            "_execute_tool",
            AsyncMock(return_value={"results": ["定义正文"]}),
        ) as execute_tool,
        patch.object(agent_service, "_log_call", AsyncMock()),
        patch.object(agent_service.client.chat.completions, "create", create),
    ):
        events = asyncio.run(collect_events())

    assert [event["content"] for event in events if event["type"] == "content"] == [
        "第3.5条的正式定义。"
    ]
    assert execute_tool.await_count == 1
    assert events[-1]["type"] == "done"
