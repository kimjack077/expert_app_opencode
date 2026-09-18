import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from app.models.audit_project import AuditProject, AuditPlanItem, AuditTeamMember
from app.models.user import User
from app.services.agent_service import agent_service
from app.services.agent_actions import execute_action
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


def test_chat_stream_recovers_when_model_returns_empty_after_tools():
    db = AsyncMock()
    tool_call = _tool_call(
        0,
        "call-1",
        "search_audit_knowledge",
        '{"query":"项目资料缺什么"}',
    )
    create = AsyncMock(
        side_effect=[
            _stream_response(_chunk(None, [tool_call])),
            _stream_response(_chunk(content="")),  # empty final turn
            # non-stream recovery path
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=""))]
            ),
        ]
    )

    async def collect_events():
        return [
            event
            async for event in agent_service.chat_stream(
                message="检查当前项目资料还缺什么，并列出引用来源。",
                context={"project_id": str(uuid4())},
                conversation=[],
                db=db,
            )
        ]

    tool_payload = {
        "query": "项目资料缺什么",
        "results": [
            {
                "source_scope": "project",
                "document_title": "管理手册",
                "content": "组织应建立质量管理体系",
                "similarity": 0.8,
            }
        ],
    }

    with (
        patch.object(agent_service, "_build_context", AsyncMock(return_value={})),
        patch.object(
            agent_service,
            "_execute_tool",
            AsyncMock(return_value=tool_payload),
        ),
        patch.object(agent_service, "_log_call", AsyncMock()),
        patch.object(agent_service.client.chat.completions, "create", create),
    ):
        events = asyncio.run(collect_events())

    content_events = [e for e in events if e["type"] == "content"]
    assert len(content_events) == 1
    assert "管理手册" in content_events[0]["content"]
    assert "引用来源" in content_events[0]["content"] or "知识检索" in content_events[0]["content"]
    assert events[-1]["type"] == "done"
    assert not any(e["type"] == "error" for e in events)


def test_get_audit_team_members():
    project_id = uuid4()
    member_user_id = uuid4()

    project = SimpleNamespace(
        id=project_id,
        title="三体系认证审核项目",
        certification_systems=["Q", "E", "S"],
        is_deleted=False,
    )
    user = SimpleNamespace(
        id=member_user_id,
        username="auditor_zhang",
        full_name="张三",
        is_deleted=False,
    )
    member = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        member_id=member_user_id,
        role="leader",
        responsible_systems=["Q", "E"],
        registration_no="2022-N1QMS-001",
        registration_level="senior",
        qualification_codes=["10.01"],
        assigned_areas=["管理层", "质检部"],
        is_deleted=False,
    )

    db = AsyncMock()
    db.get.return_value = project

    execute_result = Mock()
    execute_result.all.return_value = [(member, user)]
    db.execute.return_value = execute_result

    result = asyncio.run(
        agent_service._tool_get_audit_team_members(
            {"project_id": str(project_id)},
            {"project_id": str(project_id)},
            db,
        )
    )

    assert result["project_id"] == str(project_id)
    assert result["total_members"] == 1
    assert result["members"][0]["name"] == "张三"
    assert result["members"][0]["role_display"] == "组长"
    assert result["members"][0]["responsible_systems"] == ["Q", "E"]


def test_propose_add_team_member():
    project_id = uuid4()
    user_id = uuid4()

    project = SimpleNamespace(
        id=project_id,
        title="三体系认证审核项目",
        certification_systems=["Q", "E", "S"],
        is_deleted=False,
    )
    user = SimpleNamespace(
        id=user_id,
        username="auditor_li",
        full_name="李四",
        is_deleted=False,
    )

    db = AsyncMock()
    db.get.return_value = project

    # User search mock
    user_res = Mock()
    user_res.scalar_one_or_none.return_value = user

    # Existing member check mock (empty -> not in team)
    existing_res = Mock()
    existing_res.scalar_one_or_none.return_value = None

    db.execute.side_effect = [user_res, existing_res]

    result = asyncio.run(
        agent_service._tool_propose_add_team_member(
            {
                "member_name": "李四",
                "role": "member",
                "responsible_systems": ["Q"],
            },
            {"project_id": str(project_id)},
            db,
        )
    )

    assert result["type"] == "action_proposal"
    assert result["action"] == "add_team_member"
    assert result["data"]["member_name"] == "李四"
    assert result["data"]["role"] == "member"
    assert result["data"]["role_display"] == "组员"
    assert result["data"]["responsible_systems"] == ["Q"]


def test_execute_action_add_team_member():
    from app.services.agent_actions import execute_action

    project_id = uuid4()
    user_id = uuid4()

    project = SimpleNamespace(
        id=project_id,
        title="三体系认证审核项目",
        certification_systems=["Q", "E", "S"],
        is_deleted=False,
    )
    admin_user = SimpleNamespace(
        id=uuid4(),
        role="super_admin",
        is_deleted=False,
    )
    target_user = SimpleNamespace(
        id=user_id,
        username="auditor_wang",
        full_name="王五",
        auditor_registration_no="2022-N1-002",
        auditor_level="intermediate",
        qualified_industry_codes=["12.01"],
        is_deleted=False,
    )

    db = AsyncMock()
    # db.get is called for AuditProject and User
    db.get.side_effect = lambda model, id_: project if str(id_) == str(project_id) else target_user

    # Mock db.execute for get_project_or_404 and existing member check
    project_res = Mock()
    project_res.scalar_one_or_none.return_value = project

    existing_res = Mock()
    existing_res.scalar_one_or_none.return_value = None

    db.execute.side_effect = [project_res, existing_res]

    result = asyncio.run(
        execute_action(
            db,
            admin_user,
            "add_team_member",
            {
                "project_id": str(project_id),
                "member_id": str(user_id),
                "member_name": "王五",
                "role": "expert",
                "responsible_systems": ["E", "S"],
            },
        )
    )

    assert result["applied"] == "add_team_member"
    assert result["member_name"] == "王五"
    assert result["role"] == "expert"
    assert result["responsible_systems"] == ["E", "S"]
    assert db.add.called
    assert db.commit.called


def test_get_audit_plan_items():
    project_id = uuid4()
    plan_item_id = uuid4()
    auditor_id = uuid4()

    project = AuditProject(
        id=project_id,
        title="国投检测三体系审核",
        certification_systems=["Q", "E", "S"],
        is_deleted=False,
    )
    plan_item = AuditPlanItem(
        id=plan_item_id,
        project_id=project_id,
        plan_date=date(2026, 8, 25),
        time_start="08:30",
        time_end="12:00",
        area_name="首次会议及最高管理层",
        area_type="leadership",
        group_no="ABCDE",
        assigned_member_ids=[auditor_id],
        certification_systems=["Q", "E", "S"],
        clauses=["4.1", "4.2", "5.1", "5.2"],
        activity_type="opening_meeting",
        status="pending",
        is_deleted=False,
    )
    team_member = AuditTeamMember(
        id=uuid4(),
        project_id=project_id,
        member_id=auditor_id,
        role="leader",
        is_deleted=False,
    )
    user = User(
        id=auditor_id,
        username="zhangjg",
        full_name="张建国",
        is_deleted=False,
    )

    db = AsyncMock()
    db.get.return_value = project

    team_res = Mock()
    team_res.all.return_value = [(team_member, user)]

    plan_res = Mock()
    plan_res.scalars.return_value.all.return_value = [plan_item]

    db.execute.side_effect = [team_res, plan_res]

    result = asyncio.run(
        agent_service._tool_get_audit_plan_items(
            {"project_id": str(project_id)},
            {},
            db,
        )
    )

    assert result["total_items"] == 1
    assert result["plan_items"][0]["area_name"] == "首次会议及最高管理层"
    assert result["plan_items"][0]["assigned_member_names"] == ["张建国"]
    assert result["plan_items"][0]["certification_systems"] == ["Q", "E", "S"]


def test_propose_create_audit_plan():
    project_id = uuid4()
    auditor_id = uuid4()

    project = AuditProject(
        id=project_id,
        title="国投检测三体系审核",
        certification_systems=["Q", "E", "S"],
        is_deleted=False,
    )
    team_member = AuditTeamMember(
        id=uuid4(),
        project_id=project_id,
        member_id=auditor_id,
        role="leader",
        is_deleted=False,
    )
    user = User(
        id=auditor_id,
        username="zhangjg",
        full_name="张建国",
        is_deleted=False,
    )

    db = AsyncMock()
    db.get.return_value = project

    team_res = Mock()
    team_res.all.return_value = [(team_member, user)]
    db.execute.return_value = team_res

    plan_items = [
        {
            "plan_date": "2026-08-25",
            "time_start": "08:30",
            "time_end": "12:00",
            "area_name": "首次会议及高层访谈",
            "assigned_member_names": ["张建国"],
            "certification_systems": ["Q", "S"],
            "clauses": ["4.1", "5.1"],
        },
        {
            "plan_date": "2026-08-25",
            "time_start": "13:30",
            "time_end": "17:00",
            "area_name": "环境安全科",
            "assigned_member_names": ["王芳"],
            "certification_systems": ["E"],
            "clauses": ["6.1", "8.1"],
        },
    ]

    proposal = asyncio.run(
        agent_service._tool_propose_create_audit_plan(
            {"project_id": str(project_id), "plan_items": plan_items},
            {},
            db,
        )
    )

    assert proposal["type"] == "action_proposal"
    assert proposal["action"] == "create_audit_plan"
    assert proposal["data"]["total_items"] == 2
    assert len(proposal["data"]["plan_items"]) == 2
    assert proposal["data"]["plan_items"][0]["area_name"] == "首次会议及高层访谈"


def test_execute_action_create_audit_plan():
    project_id = uuid4()
    user_id = uuid4()

    admin_user = User(
        id=user_id,
        username="admin",
        full_name="系统管理员",
        role="admin",
        is_deleted=False,
    )
    project = AuditProject(
        id=project_id,
        title="国投检测三体系审核",
        certification_systems=["Q", "E", "S"],
        enterprise_id=None,
        is_deleted=False,
    )

    db = AsyncMock()
    db.get.return_value = project

    team_res = Mock()
    team_res.all.return_value = []
    db.execute.return_value = team_res

    plan_items = [
        {
            "plan_date": "2026-08-25",
            "time_start": "08:30",
            "time_end": "12:00",
            "area_name": "首次会议及管理层",
            "assigned_member_names": ["张建国"],
            "certification_systems": ["Q"],
            "clauses": ["4.1", "5.1"],
        }
    ]

    result = asyncio.run(
        execute_action(
            db,
            admin_user,
            "create_audit_plan",
            {
                "project_id": str(project_id),
                "plan_items": plan_items,
            },
        )
    )

    assert result["applied"] == "create_audit_plan"
    assert result["created_count"] == 1
    assert result["plan_items"][0]["area_name"] == "首次会议及管理层"
    assert db.add.called
    assert db.commit.called


def test_propose_create_meeting():
    project_id = uuid4()
    project = AuditProject(
        id=project_id,
        title="国投检测三体系审核",
        certification_systems=["Q", "E", "S"],
        enterprise_id=None,
        is_deleted=False,
    )
    db = AsyncMock()
    db.get.return_value = project

    team_res = Mock()
    team_res.all.return_value = []
    db.execute.return_value = team_res

    proposal = asyncio.run(
        agent_service._tool_propose_create_meeting(
            {
                "project_id": str(project_id),
                "meeting_type": "opening",
                "meeting_time": "2026-08-21 08:30",
                "participants_enterprise": "总经理、副总经理及各部门负责人",
                "participants_audit_team_desc": "A组和B组全体成员",
                "key_points": "确认审核目的与范围",
            },
            {},
            db,
        )
    )

    assert proposal["type"] == "action_proposal"
    assert proposal["action"] == "create_meeting_record"
    assert proposal["data"]["meeting_type"] == "opening"
    assert proposal["data"]["meeting_type_display"] == "首次会议"
    assert "2026-08-21 08:30" in proposal["data"]["meeting_time"]


def test_execute_action_create_meeting_record():
    project_id = uuid4()
    user_id = uuid4()

    admin_user = User(
        id=user_id,
        username="admin",
        full_name="系统管理员",
        role="admin",
        is_deleted=False,
    )
    project = AuditProject(
        id=project_id,
        title="国投检测三体系审核",
        certification_systems=["Q", "E", "S"],
        enterprise_id=None,
        is_deleted=False,
    )

    db = AsyncMock()
    db.get.return_value = project

    # db.execute 同时服务于「会议唯一性守卫」（.scalars().first() → None）
    # 与「审核组成员查询」（.all() → []），mock 需同时兼容两种消费方式。
    exec_result = Mock()
    scalars_mock = Mock()
    scalars_mock.first.return_value = None
    exec_result.scalars.return_value = scalars_mock
    exec_result.all.return_value = []
    db.execute.return_value = exec_result

    result = asyncio.run(
        execute_action(
            db,
            admin_user,
            "create_meeting_record",
            {
                "project_id": str(project_id),
                "meeting_type": "opening",
                "meeting_time": "2026-08-21 08:30",
                "participants_enterprise": "总经理及主管",
                "participant_names": ["张建国", "王芳"],
                "key_points": "明确审核日程与分工",
            },
        )
    )

    assert result["applied"] == "create_meeting_record"
    assert result["meeting_type"] == "opening"
    assert result["meeting_type_display"] == "首次会议"
    assert db.add.called
    assert db.commit.called




