"""软删除工具函数 + 级联策略。

═══════════════════════════════════════════════════════════════════════════
 为什么需要「级联策略表」而不是一个简单的 cascade=True
═══════════════════════════════════════════════════════════════════════════
全库共有 **84 条**「指向可软删父表」的外键关系，其中 **35 组**实测已出现
「父表已软删、子表仍有存活行」（``scripts/probe_cascade_gaps.py``）。
但其中**相当一部分是有意设计**，不能一律级联：

* ``inspection_records.template_id → inspection_templates``（13 条）
  —— ``delete_template`` 的文档明确写着「历史检查记录、审核计划等引用此模板的
  记录仍可正常访问」。模板删了**必须保留**历史记录，否则客户的历史审核数据凭空消失。
* ``audit_projects.enterprise_id → enterprises``、``inspection_records.enterprise_id``
  —— 企业归档不应该删掉业务记录。
* ``template_items.template_id → inspection_templates``（191 条）
  —— 同上，删除文档写明「保留模板及其检查项的原始数据」。

而另一部分是**明确的缺陷**：

* ``audit_plan_items.project_id → audit_projects``（27 条）
  —— 外部测试 P0-29 的根因：「我的审核任务」列出这些任务，点进去必定 404。
* ``inspection_record_items.record_id → inspection_records``（189 条）
  —— ORM 已声明 ``cascade="all, delete-orphan"``，说明设计意图就是随记录删除，
  只是软删除没触发它。

**所以这不是一个可以用 ``cascade=True`` 解决的问题，而是一张需要逐条决策的策略表。**
本模块把它显式化：每个关系都要登记策略，未登记的默认 **PRESERVE**（安全默认）。

当前登记状态（84 / 84 全覆盖）：PRESERVE 56 · CASCADE_HARD 21 · CASCADE_SOFT 7。
其中 32 条「用户归属字段」是同一决策的 32 个实例，程序化登记
（见 :func:`_register_user_attribution`），不逐个抄写。

另有 **1 条间接级联**（:data:`INDIRECT_CASCADE_POLICY`）：外键不在目标表上、
FK 图表达不了的归属关系，必须显式声明（「删除项目 → 处理其检查任务」）。

═══════════════════════════════════════════════════════════════════════════
 三种策略
═══════════════════════════════════════════════════════════════════════════
    PRESERVE      不动子行。父已删、子仍存活 —— 这是**有意**的。
    CASCADE_SOFT  子行一并置 is_deleted / deleted_at（**可逆**，可恢复）
    CASCADE_HARD  子行**物理删除**（不可逆）。仅用于「无 is_deleted 列的
                  依赖明细表」——这类表本就无法软删，留着就是永久孤儿。

``tests/test_soft_delete_cascade.py`` 强制要求：**所有指向可软删父表的外键关系
都必须在本表登记**。新加一个外键却忘了决策，测试会立刻失败并打印该关系，
而不是等到线上出现孤儿数据。
"""

from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# 策略常量
# ---------------------------------------------------------------------------
PRESERVE = "preserve"
CASCADE_SOFT = "cascade_soft"
CASCADE_HARD = "cascade_hard"

# ---------------------------------------------------------------------------
# 级联策略表
# ---------------------------------------------------------------------------
# 键：(子表, 子列, 父表)；值：(策略, 理由)
#
# 理由必须写清楚 —— 半年后有人问"为什么模板删了不删检查项"，
# 答案就在这一行里，不用去翻 git log。
FK_CASCADE_POLICY: dict[tuple[str, str, str], tuple[str, str]] = {
    # ── 审核项目 → 其项目级附属数据 ──────────────────────────────────
    # 项目是聚合根：区域、组员、会议、不符合项、报告、证据、AI 会话
    # 在项目消失后都失去归属与展示入口。
    ("audit_plan_items", "project_id", "audit_projects"): (
        CASCADE_SOFT,
        "计划项是项目的执行单元。父项目已删但计划项仍存活时，「我的审核任务」"
        "会列出这些任务、点进去必定 404（外部测试 P0-29 根因）。",
    ),
    ("audit_areas", "project_id", "audit_projects"): (
        CASCADE_HARD,
        "审核区域是项目的组织维度，无 is_deleted 列；项目没了区域即无意义。",
    ),
    ("audit_area_records", "project_id", "audit_projects"): (
        CASCADE_HARD,
        "区域记录是项目现场记录的载体，无 is_deleted 列，随项目一并清除。",
    ),
    ("audit_team_members", "project_id", "audit_projects"): (
        CASCADE_SOFT,
        "审核组成员名单脱离项目后无展示入口，保留会出现在成员相关查询里。",
    ),
    ("communication_meetings", "project_id", "audit_projects"): (
        CASCADE_HARD,
        "沟通会议记录属项目过程材料，无 is_deleted 列。",
    ),
    ("nonconformities", "project_id", "audit_projects"): (
        CASCADE_HARD,
        "不符合项是项目结论的一部分，无 is_deleted 列。",
    ),
    ("audit_reports", "project_id", "audit_projects"): (
        CASCADE_HARD,
        "项目报告脱离项目后无法访问，无 is_deleted 列。",
    ),
    ("ai_audit_sessions", "project_id", "audit_projects"): (
        CASCADE_HARD,
        "AI 审核会话是过程数据，无 is_deleted 列。",
    ),
    ("ai_draft_records", "project_id", "audit_projects"): (
        CASCADE_HARD,
        "AI 草稿记录是过程数据，无 is_deleted 列。",
    ),
    ("evidence_items", "project_id", "audit_projects"): (
        CASCADE_HARD,
        "证据条目挂靠项目，无 is_deleted 列。",
    ),
    ("evidence_submissions", "project_id", "audit_projects"): (
        CASCADE_HARD,
        "证据提交记录挂靠项目，无 is_deleted 列。",
    ),
    ("project_knowledge_chunks", "project_id", "audit_projects"): (
        CASCADE_HARD,
        "项目知识分片是 RAG 检索缓存，无 is_deleted 列；项目删除后分片必须清掉，"
        "否则检索会召回已删项目的内容。",
    ),
    ("project_documents", "project_id", "audit_projects"): (
        CASCADE_SOFT,
        "项目文档属项目材料，支持软删，可随项目一并归档。",
    ),
    # ── 检查记录 / 任务 → 明细 ────────────────────────────────────────
    ("inspection_record_items", "record_id", "inspection_records"): (
        CASCADE_HARD,
        "ORM 已声明 cascade='all, delete-orphan'，设计意图即随记录删除；"
        "该表无 is_deleted 列，软删记录后明细会成为永久孤儿（实测 189 条）。",
    ),
    ("task_item_records", "task_id", "inspection_tasks"): (
        CASCADE_HARD,
        "同上：任务明细表无 is_deleted 列，任务软删后明细成为永久孤儿"
        "（实测 186 条），且会被明细级统计重复计入。",
    ),
    # ── 审核计划项 → 其附属数据 ───────────────────────────────────────
    # ⚠ 判据：``delete_plan_item``（audit_projects.py:807）是**审核员的日常操作**
    #   —— 移除一项检查任务。凡是「现场检查记录 / 不符合项 / 证据」这类
    #   **业务结论与证据**，都不得因日常操作被销毁 → 一律 PRESERVE。
    #   只有**派生缓存**（AI 草稿）才允许级联，因为可重新生成。
    ("audit_area_records", "plan_item_id", "audit_plan_items"): (
        PRESERVE,
        "**有意保留**：现场检查记录是审核证据。移除一项检查任务不等于作废"
        "已完成的现场检查——记录仍挂在项目下（project_id）可供报告引用。"
        "该表无 is_deleted 列，硬级联会永久销毁现场数据。",
    ),
    ("evidence_submissions", "plan_item_id", "audit_plan_items"): (
        PRESERVE,
        "**有意保留**：证据提交是审核证据。移除检查任务不得销毁已提交的证据。",
    ),
    ("ai_draft_records", "plan_item_id", "audit_plan_items"): (
        CASCADE_HARD,
        "AI 草稿是**可重生成的过程缓存**，非业务结论；计划项删除后草稿失去归属，"
        "无 is_deleted 列。",
    ),
    ("nonconformities", "plan_item_id", "audit_plan_items"): (
        PRESERVE,
        "**有意保留**：不符合项是**项目级结论**，是审核报告与后续整改的依据。"
        "移除一项检查任务不得作废已经判定的不符合项（其归属是 project_id）。",
    ),
    # ── 文档 / 媒体 → 派生数据 ────────────────────────────────────────
    ("project_knowledge_chunks", "document_id", "project_documents"): (
        CASCADE_HARD,
        "文档删除后其知识分片必须清除，否则检索会召回已删文档的内容。",
    ),
    ("knowledge_embeddings", "document_id", "knowledge_documents"): (
        CASCADE_HARD,
        "同上：文档删除后向量必须清除，否则问答会引用已删文档。",
    ),
    ("photo_analyses", "media_file_id", "media_files"): (
        CASCADE_HARD,
        "照片分析结果是该图片的派生物，图片删除后无意义，无 is_deleted 列。",
    ),
    # ── 任务 → 媒体 ───────────────────────────────────────────────────
    ("media_files", "task_id", "inspection_tasks"): (
        CASCADE_SOFT,
        "任务附件随任务归档；支持软删，保留可恢复性。",
    ),
    # ── 明确「不级联」的关系（有意保留，逐条给出理由）────────────────
    ("inspection_records", "template_id", "inspection_templates"): (
        PRESERVE,
        "**有意保留**：delete_template 文档明确「历史检查记录、审核计划等引用此模板的"
        "记录仍可正常访问」。模板删除不得删除客户的历史审核数据。"
        "记录另存有 template_snapshot，内容可独立还原。",
    ),
    ("inspection_records", "enterprise_id", "enterprises"): (
        PRESERVE,
        "**有意保留**：企业归档不应删除其历史检查记录（审计追溯需要）。",
    ),
    ("audit_projects", "enterprise_id", "enterprises"): (
        PRESERVE,
        "**有意保留**：企业归档不应删除其审核项目。",
    ),
    ("template_items", "template_id", "inspection_templates"): (
        PRESERVE,
        "**有意保留**：delete_template 文档明确「保留模板及其检查项的原始数据」，"
        "以便管理员按 URL 回看历史模板结构。",
    ),
    ("audit_plan_items", "template_id", "inspection_templates"): (
        PRESERVE,
        "**有意保留**：计划项引用的是模板快照来源，模板删除不影响历史计划。",
    ),
    ("inspection_tasks", "template_id", "inspection_templates"): (
        PRESERVE,
        "**有意保留**：任务引用的是模板快照来源，模板删除不影响历史任务。",
    ),
    ("audit_area_records", "template_id", "inspection_templates"): (
        PRESERVE,
        "**有意保留**：区域记录引用模板快照来源，属历史材料。",
    ),
    ("task_item_records", "template_item_id", "template_items"): (
        PRESERVE,
        "**有意保留**：任务明细引用的是模板项的原始定义，是历史判定的依据；"
        "且该表为硬删除表，级联会丢失历史判定口径。",
    ),
    ("audit_plan_items", "inspection_task_id", "inspection_tasks"): (
        PRESERVE,
        "**有意保留**：计划项与任务是多对一桥接，任务删除不应反向删除计划项"
        "（计划项归属项目，由项目级策略负责）。",
    ),
    ("enterprise_qualifications", "enterprise_id", "enterprises"): (
        PRESERVE,
        "**有意保留**：企业资质是历史档案，随企业归档保留。",
    ),
    ("enterprise_products", "enterprise_id", "enterprises"): (
        PRESERVE,
        "**有意保留**：企业产品是历史档案，随企业归档保留。",
    ),
    ("rectification_records", "enterprise_id", "enterprises"): (
        PRESERVE,
        "**有意保留**：整改记录是企业侧的整改历史，企业归档不得销毁。"
        "注：ORM 上声明了 delete-orphan，企业硬删会连带销毁——目前无此路径。",
    ),
    ("template_recommendations", "enterprise_id", "enterprises"): (
        PRESERVE,
        "**有意保留**：推荐记录是历史留痕，企业归档后仍可回看推荐依据。",
    ),
    ("template_recommendations", "template_id", "inspection_templates"): (
        PRESERVE,
        "**有意保留**：与 inspection_records.template_id 同口径——"
        "模板删除不得销毁引用它的历史记录。",
    ),
    ("rectification_records", "task_id", "inspection_tasks"): (
        PRESERVE,
        "**有意保留**：整改记录是企业侧业务历史，任务删除不销毁历史。"
        "该表无 is_deleted 列，硬级联会永久丢失整改证据。",
    ),
    ("evidence_items", "source_document_id", "project_documents"): (
        PRESERVE,
        "**有意保留**：source_document_id 是**来源引用**（出处留痕），非归属关系。"
        "证据条目挂靠的是 project_id，文档删除不应连带删除证据。",
    ),
    ("inspection_record_items", "template_item_id", "template_items"): (
        PRESERVE,
        "**有意保留**：检查记录明细引用模板项定义，是历史判定的依据。"
        "该表为硬删除表，级联会丢失历史判定口径（同 task_item_records 的处理）。",
    ),
    # ── 新增的级联（本轮核查后确认）────────────────────────────────────
    ("template_items", "parent_id", "template_items"): (
        CASCADE_SOFT,
        "**真缺陷**：templates.py::build_tree 以 parent_id=None 为根，父分类软删后"
        "子项的 parent_id 指向已删节点，永远挂不进树——界面少显示，"
        "而 items_count_query 仍把它们计入 total_items，"
        "出现「列表说 10 项、编辑器只显示 7 项」的对不上账。"
        "子项随父项一并软删，两处口径重新一致，且可恢复。",
    ),
    ("media_files", "project_id", "audit_projects"): (
        CASCADE_SOFT,
        "项目附件随项目归档。media_files 支持软删，保留可恢复性"
        "（与 media_files.task_id 同策略）。",
    ),
    ("project_artifacts", "project_id", "audit_projects"): (
        CASCADE_SOFT,
        "项目产出物脱离项目后无展示入口（project_agent.py 的列表接口按 project_id"
        "过滤）。ORM 已声明 delete-orphan，此处用软删保持可恢复。",
    ),
    ("check_item_regulations", "template_item_id", "template_items"): (
        CASCADE_HARD,
        "纯关联表（CheckItemRegulation 文档明确 association table），"
        "两个外键都声明了 ondelete='CASCADE'，无 is_deleted 列。"
        "模板项删除后关联行即死链接，留着会被 RAG 召回。",
    ),
    ("check_item_regulations", "knowledge_document_id", "knowledge_documents"): (
        CASCADE_HARD,
        "同上：纯关联表。knowledge.py::delete_document 已手动硬删 KnowledgeEmbedding，"
        "但漏了 check_item_regulations——本条补上这个缺口。",
    ),
    # ── 归属字段（→ users）：见文件末尾 _register_user_attribution() ──
    # 这 32 条语义高度一致（"谁做的/谁负责"），用程序化登记避免同质条目淹没策略表。
}

# ---------------------------------------------------------------------------
# 用户归属字段：32 条 → users
# ---------------------------------------------------------------------------
# 为什么单独成块：这 32 条不是"待决策项"，而是**同一决策的 32 个实例**。
# 逐个抄写只会让策略表被同质条目淹没，反而看不出真正的取舍。
#
# 决策：一律 PRESERVE。删除/停用用户**绝不能**删除其创建、审核、负责的业务记录——
# 审计追溯依赖这些字段，删掉记录等于销毁追责链条。
# 正确处置是**停用账号**（is_active=False），而非级联清理数据。
_USERS_AUDIT_TRAIL: tuple[tuple[str, str], ...] = (
    # (子表, 子列) —— 全部指向 users.id
    ("agent_conversations", "user_id"),
    ("agent_memories", "user_id"),
    ("ai_audit_sessions", "created_by"),
    ("ai_draft_records", "confirmed_by"),
    ("audit_area_records", "recorded_by"),
    ("audit_logs", "user_id"),
    ("audit_projects", "created_by"),
    ("audit_reports", "approved_by"),
    ("audit_reports", "prepared_by"),
    ("audit_reports", "reviewed_by"),
    ("communication_meetings", "created_by"),
    ("evidence_submissions", "submitted_by"),
    ("inspection_guidelines", "created_by"),
    ("inspection_tasks", "assigned_by"),
    ("inspection_templates", "created_by"),
    ("knowledge_documents", "created_by"),
    ("llm_call_logs", "user_id"),
    ("media_files", "uploaded_by"),
    ("nonconformities", "confirmed_by"),
    ("nonconformities", "created_by"),
    ("nonconformities", "verified_by"),
    ("project_artifacts", "created_by"),
    ("project_documents", "created_by"),
    ("rectification_records", "created_by"),
    ("rectification_records", "reviewer"),
    ("task_item_records", "recorded_by"),
    ("template_items", "created_by"),
    ("template_recommendations", "created_by"),
)

_USERS_ASSIGNMENT: tuple[tuple[str, str], ...] = (
    # 语义与审计字段略有不同：这是"这个人负责/参与"，是**业务事实**而非操作留痕。
    # 但结论相同——用户离职停用后，其历史任务与记录必须可追溯，不能级联删除。
    ("audit_projects", "team_leader_id"),
    ("audit_team_members", "member_id"),
    ("inspection_records", "inspector_id"),
    ("inspection_tasks", "assigned_to"),
)


def _register_user_attribution() -> None:
    """把 32 条用户归属关系登记进策略表（一律 PRESERVE）。"""
    audit_reason = (
        "**有意保留**：审计归属字段（谁创建/审核/确认的）。删除用户不得删除其"
        "业务记录——审计追溯依赖该字段，正确处置是停用账号而非级联清理数据。"
    )
    assignment_reason = (
        "**有意保留**：人员归属字段（谁负责/参与）。用户离职停用后，其历史任务"
        "与检查记录仍须可追溯，不得随用户级联删除。"
    )
    for child_table, child_column in _USERS_AUDIT_TRAIL:
        FK_CASCADE_POLICY[(child_table, child_column, "users")] = (
            PRESERVE,
            audit_reason,
        )
    for child_table, child_column in _USERS_ASSIGNMENT:
        FK_CASCADE_POLICY[(child_table, child_column, "users")] = (
            PRESERVE,
            assignment_reason,
        )


def _register_category_references() -> None:
    """分类 / 层级引用：一律 PRESERVE。

    分类（行业、组织、父级）是**维度**而非**归属**：删掉一个行业分类，
    不等于要删掉挂在该分类下的企业、模板、用户。

    ``industries.parent_id`` 特别说明：``industries.py`` 的树构建逻辑
    （第 54-57 行）在父节点缺失时会把子节点**提升为顶级**，不会丢数据——
    这是可接受的降级行为，无需级联。
    """
    entries = {
        ("enterprises", "industry_id", "industries"):
            "行业分类是维度，企业归档不等于删除企业；分类删除后企业仅失去归类。",
        ("inspection_templates", "industry_id", "industries"):
            "同上：模板的行业归类是维度，模板不随分类删除。",
        ("users", "industry_id", "industries"):
            "同上：用户的行业属性是维度，用户不随分类删除。",
        ("users", "org_id", "organizations"):
            "组织归属是维度；组织停用后用户仍需保留（由停用流程单独处理）。",
        ("industries", "parent_id", "industries"):
            "父分类删除后，子分类由 industries.py 的树构建逻辑提升为顶级，不丢数据。",
    }
    for relation, note in entries.items():
        FK_CASCADE_POLICY[relation] = (PRESERVE, f"**有意保留**：{note}")


_register_user_attribution()
_register_category_references()

# ---------------------------------------------------------------------------
# 间接级联（归属关系的外键不在目标表上）
# ---------------------------------------------------------------------------
# 有些归属关系**无法从 information_schema 推导**，必须显式登记：
# 外键不在目标表上，目标表反而是"父"。
#
# 典型：``inspection_tasks`` 是 ``audit_plan_items`` 的**父表**
# （外键 ``audit_plan_items.inspection_task_id`` 在计划项一侧）。
# 于是「删除审核项目时也要删掉它的检查任务」这条规则在 FK 图上**根本不存在**——
# 但它是一条真实且必须的规则，见下面的理由。
#
# 键：(被删父表, 经由表, 经由表的父列)
# 值：(经由表的外键列, 目标表, 策略, 理由)  —— 目标侧固定匹配 ``目标表.id``
INDIRECT_CASCADE_POLICY: dict[tuple[str, str, str], tuple[str, str, str, str]] = {
    ("audit_projects", "audit_plan_items", "project_id"): (
        "inspection_task_id",
        "inspection_tasks",
        CASCADE_SOFT,
        "**真缺陷（P0-29 同类，换了张表）**：``create_plan_item`` 会**自动创建**"
        "InspectionTask。删除项目时若不删任务，任务仍留在审核员的「我的任务」列表里"
        "—— ``tasks.py`` 的列表只过滤 ``InspectionTask.is_deleted``，不看项目是否已删；"
        "同时因计划项已软删，``audit_project_id`` / ``area_name`` 回填不到，"
        "卡片失去全部上下文，点进去无从定位。软删可逆，与计划项状态保持一致。",
    ),
}


# 建索引，便于按子表快速取策略
_POLICY_INDEX: dict[tuple[str, str], tuple[str, str, str]] = {
    (child_table, child_column): (parent_table, policy, reason)
    for (child_table, child_column, parent_table), (policy, reason) in FK_CASCADE_POLICY.items()
}


def policy_for(
    child_table: str, child_column: str, parent_table: str
) -> tuple[str, str]:
    """返回 ``(策略, 理由)``；未登记的关系返回 **PRESERVE**。

    安全默认是刻意的：**宁可留下孤儿，也不可误删数据**。
    未登记的关系由 ``tests/test_soft_delete_cascade.py`` 强制要求补齐。
    """
    entry = _POLICY_INDEX.get((child_table, child_column))
    if entry and entry[0] == parent_table:
        return entry[1], entry[2]
    return PRESERVE, "未登记，采用安全默认（不级联）"


def registered_child_tables() -> dict[str, list[tuple[str, str, str]]]:
    """按子表归集策略，供文档与测试使用。"""
    grouped: dict[str, list[tuple[str, str, str]]] = {}
    for (child_table, child_column, parent_table), (policy, reason) in FK_CASCADE_POLICY.items():
        grouped.setdefault(child_table, []).append((child_column, parent_table, policy))
    return grouped


# ---------------------------------------------------------------------------
# 单对象软删除
# ---------------------------------------------------------------------------


async def soft_delete(
    db: AsyncSession,
    obj,
    unique_fields: Optional[Iterable[str]] = None,
) -> None:
    """对对象执行软删除（不含级联，级联见 :func:`soft_delete_cascade`）。

    - 设置 is_deleted=True, deleted_at=now
    - 对 unique_fields 中的字段追加 _deleted_<timestamp> 后缀，
      避免软删除记录阻塞新记录的创建（唯一约束冲突）。

    Args:
        db: 异步会话
        obj: ORM 对象（需具备 is_deleted / deleted_at 字段）
        unique_fields: 需要重命名的唯一字段列表，如 ['username', 'email']
    """
    obj.is_deleted = True
    obj.deleted_at = datetime.now(timezone.utc)

    # 账号软删必须同步停用，否则 is_active=True 的幽灵账号仍可被鉴权链路碰到
    if hasattr(obj, "is_active"):
        obj.is_active = False

    if unique_fields:
        stamp = int(datetime.now(timezone.utc).timestamp())
        suffix = f"_deleted_{stamp}"
        for field_name in unique_fields:
            current = getattr(obj, field_name, None)
            if not current or not isinstance(current, str):
                continue
            if "_deleted_" in current:
                continue
            if field_name == "email" and "@" in current:
                # 保持 EmailStr/唯一约束兼容：local+deleted<ts>@domain
                local, _, domain = current.partition("@")
                new_val = f"{local}+deleted{stamp}@{domain}"
            else:
                new_val = current + suffix
            max_len = 200
            if len(new_val) > max_len:
                if field_name == "email" and "@" in new_val:
                    local, _, domain = new_val.partition("@")
                    keep = max_len - len(domain) - 1
                    new_val = f"{local[:keep]}@{domain}"
                else:
                    new_val = new_val[: max_len - len(suffix)] + suffix
            setattr(obj, field_name, new_val)

    await db.flush()


# ---------------------------------------------------------------------------
# 级联
# ---------------------------------------------------------------------------


def _child_table(parent_table_name: str) -> list[tuple[str, str, str]]:
    """列出该父表下所有**已登记且需级联**的子关系：``(子表, 子列, 策略)``。"""
    result = []
    for (child_table, child_column, parent_table), (policy, _reason) in FK_CASCADE_POLICY.items():
        if parent_table == parent_table_name and policy != PRESERVE:
            result.append((child_table, child_column, policy))
    return result


def _order_cascade_relations(
    relations: list[tuple[str, str, str]], tables,
) -> list[tuple[str, str, str]]:
    """按外键依赖将同一层的子表排成「子先父后」。"""
    if len(relations) < 2:
        return relations

    first_index = {child_table: index for index, (child_table, _, _) in enumerate(relations)}
    child_names = set(first_index)
    dependencies = {child_table: set() for child_table in child_names}
    for child_table in child_names:
        table = tables.get(child_table)
        if table is None:
            continue
        for foreign_key in table.foreign_keys:
            referred_table = foreign_key.column.table.name
            if referred_table in child_names and referred_table != child_table:
                dependencies[child_table].add(referred_table)

    remaining = set(child_names)
    ordered_names: list[str] = []
    while remaining:
        referred_by_remaining = set().union(
            *(dependencies[name] & remaining for name in remaining)
        )
        ready = [name for name in remaining if name not in referred_by_remaining]
        if not ready:
            ready = [min(remaining, key=first_index.__getitem__)]
        ready.sort(key=first_index.__getitem__)
        ordered_names.extend(ready)
        remaining.difference_update(ready)

    by_name = {child_table: (child_column, policy) for child_table, child_column, policy in relations}
    return [(name, *by_name[name]) for name in ordered_names]


# 级联的最大层数。模板分类树、项目→计划项→区域记录这类多级归属需要逐层展开；
# 正常情况下 2–3 层足够，12 层是防御性上限（配合"已软删的行不重复命中"，
# 环状关系也会自然收敛）。
MAX_CASCADE_DEPTH = 12


async def _apply_cascade(
    db: AsyncSession,
    table,
    column_name: str,
    parent_ids: list,
    policy: str,
    now: datetime,
) -> list:
    """对一张表施加一次级联，返回**实际受影响的 id 列表**（用于继续向下展开）。

    用 ``RETURNING id`` 而不是 ``rowcount``：既要计数，也要拿到 id 才能展开下一层。
    """
    if not parent_ids or "id" not in table.columns or column_name not in table.columns:
        return []

    condition = table.c[column_name].in_(parent_ids)

    if policy == CASCADE_SOFT:
        if "is_deleted" not in table.columns:
            return []
        values: dict = {"is_deleted": True}
        if "deleted_at" in table.columns:
            values["deleted_at"] = now
        stmt = (
            update(table)
            .where(condition, table.c.is_deleted.is_(False))
            .values(**values)
            .returning(table.c.id)
            .execution_options(synchronize_session=False)
        )
    else:  # CASCADE_HARD
        stmt = (
            delete(table)
            .where(condition)
            .returning(table.c.id)
            .execution_options(synchronize_session=False)
        )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _resolve_indirect_ids(
    db: AsyncSession,
    via_table,
    via_parent_column: str,
    via_fk_column: str,
    parent_ids: list,
) -> list:
    """经由中间表解析出间接级联的目标 id（见 :data:`INDIRECT_CASCADE_POLICY`）。"""
    if via_fk_column not in via_table.columns or via_parent_column not in via_table.columns:
        return []

    stmt = select(via_table.c[via_fk_column]).where(
        via_table.c[via_parent_column].in_(parent_ids),
        via_table.c[via_fk_column].is_not(None),
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all() if row[0] is not None]


async def soft_delete_cascade(
    db: AsyncSession,
    obj,
    unique_fields: Optional[Iterable[str]] = None,
) -> dict[str, int]:
    """软删除对象，并按策略表**逐层**处理其子行。

    返回 ``{子表: 影响行数}``，便于调用方记录审计日志与提示用户。

    处理两类规则：

    * :data:`FK_CASCADE_POLICY` —— 外键在子表上（可从 information_schema 推导）
    * :data:`INDIRECT_CASCADE_POLICY` —— 外键在别处，归属关系需显式声明

    实现说明：

    * 子行处理走**批量 UPDATE/DELETE**（不加载 ORM 对象），
      因为子行数量可能很大（实测单表上百条），逐个实例化既慢又占内存。
    * 用 ``RETURNING id`` 拿到本层实际受影响的 id，作为下一层的父 id
      —— 多级归属必须展开，否则只清掉第一层，第二层仍是孤儿。
      例如「项目 → 计划项 → 区域记录」和模板的「分类 → 子分类 → 检查项」。
    * 批量语句需要 ``synchronize_session=False`` —— 我们不依赖会话内的对象状态。
    * 收敛性：CASCADE_SOFT 只命中 ``is_deleted = False`` 的行，
      CASCADE_HARD 的行删除后不复存在，因此环状关系也会自然终止；
      ``MAX_CASCADE_DEPTH`` 只是防御性上限。
    """
    table_name = obj.__table__.name
    parent_id = obj.id

    await soft_delete(db, obj, unique_fields=unique_fields)

    affected: dict[str, int] = {}
    now = datetime.now(timezone.utc)

    from app.database import Base  # 延迟导入，避免 utils → database 的模块级耦合

    # 广度优先逐层展开
    frontier: list[tuple[str, list]] = [(table_name, [parent_id])]
    depth = 0

    while frontier and depth < MAX_CASCADE_DEPTH:
        depth += 1
        next_frontier: list[tuple[str, list]] = []

        for parent_table_name, parent_ids in frontier:
            if not parent_ids:
                continue

            # ── 1. 直接级联（外键在子表上）────────────────────────────
            child_relations = _order_cascade_relations(
                _child_table(parent_table_name), Base.metadata.tables
            )
            for child_table_name, child_column, policy in child_relations:
                table = Base.metadata.tables.get(child_table_name)
                if table is None:
                    # 表不存在（迁移未跑或模型未导入）：跳过而不是报错，
                    # 避免因局部环境差异让删除整体失败。
                    continue

                rows = await _apply_cascade(
                    db, table, child_column, parent_ids, policy, now
                )
                if rows:
                    affected[child_table_name] = affected.get(child_table_name, 0) + len(rows)
                    next_frontier.append((child_table_name, rows))

            # ── 2. 间接级联（外键在别处，归属关系显式登记）────────────
            for (p_table, via_table_name, via_parent_column), (
                via_fk_column,
                target_table_name,
                policy,
                _reason,
            ) in INDIRECT_CASCADE_POLICY.items():
                if p_table != parent_table_name:
                    continue

                via_table = Base.metadata.tables.get(via_table_name)
                target_table = Base.metadata.tables.get(target_table_name)
                if via_table is None or target_table is None:
                    continue

                target_ids = await _resolve_indirect_ids(
                    db, via_table, via_parent_column, via_fk_column, parent_ids
                )
                rows = await _apply_cascade(
                    db, target_table, "id", target_ids, policy, now
                )
                if rows:
                    affected[target_table_name] = (
                        affected.get(target_table_name, 0) + len(rows)
                    )
                    next_frontier.append((target_table_name, rows))

        frontier = next_frontier

    await db.flush()
    return affected


def not_deleted(model):
    """返回 model.is_deleted == False 的过滤条件，用于 query.where(not_deleted(Model))"""
    return model.is_deleted == False  # noqa: E712
