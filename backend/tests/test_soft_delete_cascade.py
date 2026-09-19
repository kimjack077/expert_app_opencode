"""契约层测试：软删除级联策略的完备性与安全性。

═══════════════════════════════════════════════════════════════════════════
 这个文件守住什么
═══════════════════════════════════════════════════════════════════════════
实测（``scripts/probe_cascade_gaps.py``）：全库有 **35 组**「父表已软删、
子表仍有存活行」的外键关系。但其中相当一部分是**有意设计**：

* 模板删除**必须保留**历史检查记录（``delete_template`` 文档明确要求）；
* 企业归档**不应删除**其业务记录。

因此不能一律级联 —— 那会删掉客户的真实历史数据。正确做法是**逐条决策**，
并把决策显式登记在 ``app/utils/soft_delete.py::FK_CASCADE_POLICY``。

本文件把"忘了决策"变成会失败的断言：

* **完备性** —— 所有指向可软删父表的外键关系都必须在策略表中登记。
  新加一个外键却忘了决策，测试立刻失败并打印该关系；
* **安全性** —— 未经登记的关系统一 PRESERVE（宁可留下孤儿，不可误删数据）；
* **一致性** —— 策略表里不得存在已失效的条目（外键被删了却还留着策略）。

不需要数据库（从 SQLAlchemy 元数据推导）::

    .venv\\Scripts\\python.exe -m pytest tests/test_soft_delete_cascade.py -v
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def _metadata():
    import app.models  # noqa: F401 — 触发全部模型注册
    from app.database import Base

    return Base.metadata


def _soft_deletable_tables() -> set[str]:
    """具备 ``is_deleted`` 列的表 —— 只有这些表才谈得上"父已软删"。"""
    return {
        table.name
        for table in _metadata().tables.values()
        if "is_deleted" in table.columns
    }


def _fk_relations_to_soft_parents() -> set[tuple[str, str, str]]:
    """``(子表, 子列, 父表)`` —— 所有指向可软删父表主键的外键关系。"""
    soft_tables = _soft_deletable_tables()
    relations: set[tuple[str, str, str]] = set()

    for table in _metadata().tables.values():
        for fk in table.foreign_keys:
            parent = fk.column.table.name
            if parent in soft_tables and fk.column.name == "id":
                relations.add((table.name, fk.parent.name, parent))
    return relations


def _registered_relations() -> set[tuple[str, str, str]]:
    from app.utils.soft_delete import FK_CASCADE_POLICY

    return set(FK_CASCADE_POLICY)


def test_every_fk_to_soft_deletable_parent_is_classified():
    """**核心门禁**：所有指向可软删父表的外键都必须显式登记策略。

    失败时的处置：在 ``FK_CASCADE_POLICY`` 中登记该关系，并在理由里写清楚
    「为什么级联」或「为什么保留」。**不要**为了过测试而随意选一个策略——
    选 CASCADE 意味着会删数据。
    """
    unclassified = sorted(_fk_relations_to_soft_parents() - _registered_relations())

    assert not unclassified, (
        "以下外键指向可软删的父表，但未登记级联策略：\n"
        + "\n".join(f"  {c}.{col} → {p}" for c, col, p in unclassified)
        + "\n\n请到 app/utils/soft_delete.py 的 FK_CASCADE_POLICY 中逐条登记：\n"
        "  PRESERVE      —— 有意保留（父已删、子仍存活），需说明理由\n"
        "  CASCADE_SOFT  —— 子行一并软删（可逆）\n"
        "  CASCADE_HARD  —— 子行物理删除（不可逆，仅限无 is_deleted 列的依赖明细表）\n"
    )


def test_no_stale_policy_entries():
    """策略表不得残留已失效的条目 —— 外键已被删除或改名后，策略应同步清理。"""
    stale = sorted(_registered_relations() - _fk_relations_to_soft_parents())

    assert not stale, (
        "以下策略条目已不存在对应的外键，请从 FK_CASCADE_POLICY 中删除：\n"
        + "\n".join(f"  {c}.{col} → {p}" for c, col, p in stale)
    )


def test_unregistered_relation_defaults_to_preserve():
    """安全默认：未登记的关系必须 PRESERVE，绝不能默认删数据。"""
    from app.utils.soft_delete import PRESERVE, policy_for

    policy, reason = policy_for("some_table", "some_column", "some_parent")
    assert policy == PRESERVE, "未登记关系的默认策略必须是 PRESERVE"
    assert reason, "默认策略也要有理由说明"


def test_preserve_entries_all_carry_a_reason():
    """每条 PRESERVE 都必须写清楚为什么保留 —— 否则半年后没人敢改。"""
    from app.utils.soft_delete import FK_CASCADE_POLICY, PRESERVE

    missing = [
        f"{c}.{col} → {p}"
        for (c, col, p), (policy, reason) in FK_CASCADE_POLICY.items()
        if policy == PRESERVE and len(reason.strip()) < 10
    ]
    assert not missing, (
        "以下 PRESERVE 条目缺少足够说明的理由：\n" + "\n".join(f"  {m}" for m in missing)
    )


def test_history_preserving_relations_are_not_cascaded():
    """**回归护栏**：模板/企业删除时，历史业务记录必须保留。

    这四条是本项目**明确的设计约定**（见 delete_template 文档）。
    任何人若把它们改成 CASCADE，历史审核数据会凭空消失 —— 属最高危改动。
    """
    from app.utils.soft_delete import FK_CASCADE_POLICY, PRESERVE

    must_preserve = [
        ("inspection_records", "template_id", "inspection_templates"),
        ("inspection_records", "enterprise_id", "enterprises"),
        ("audit_projects", "enterprise_id", "enterprises"),
        ("template_items", "template_id", "inspection_templates"),
    ]

    for relation in must_preserve:
        assert relation in FK_CASCADE_POLICY, f"缺少策略登记：{relation}"
        policy, _ = FK_CASCADE_POLICY[relation]
        assert policy == PRESERVE, (
            f"{relation[0]}.{relation[1]} → {relation[2]} 被改为 {policy}。\n"
            "该关系必须保留：删除模板/企业不得删除历史业务记录。"
        )


def test_plan_items_cascade_is_soft():
    """计划项随项目软删 —— 外部测试 P0-29 的修复点，必须是可逆的软删。

    硬删会让"误删项目后无法恢复计划项"，而计划项承载了审核任务列表。
    """
    from app.utils.soft_delete import CASCADE_SOFT, FK_CASCADE_POLICY

    relation = ("audit_plan_items", "project_id", "audit_projects")
    assert relation in FK_CASCADE_POLICY
    policy, reason = FK_CASCADE_POLICY[relation]
    assert policy == CASCADE_SOFT, (
        f"计划项级联策略应为 {CASCADE_SOFT}（可逆），实际 {policy}"
    )
    assert "P0-29" in reason or "404" in reason, "理由中应记录该缺陷的来源，便于追溯"


def test_plan_item_removal_must_not_destroy_business_conclusions():
    """**回归护栏**：移除一项检查任务（``delete_plan_item``，审核员的日常操作）
    不得销毁业务结论与证据。

    这三条曾是 CASCADE_HARD —— 意味着审核员删掉一个计划项，
    该任务下的不符合项、证据提交、现场检查记录会被**物理删除且不可恢复**。
    现场实测后改为 PRESERVE：这些数据归属的是项目（``project_id``），
    计划项只是来源，不能因为来源被移除就作废结论。
    """
    from app.utils.soft_delete import FK_CASCADE_POLICY, PRESERVE

    must_preserve = [
        ("nonconformities", "plan_item_id", "audit_plan_items"),
        ("evidence_submissions", "plan_item_id", "audit_plan_items"),
        ("audit_area_records", "plan_item_id", "audit_plan_items"),
    ]

    for relation in must_preserve:
        assert relation in FK_CASCADE_POLICY, f"缺少策略登记：{relation}"
        policy, _ = FK_CASCADE_POLICY[relation]
        assert policy == PRESERVE, (
            f"{relation[0]}.{relation[1]} → {relation[2]} 被登记为 {policy}。\n"
            "该关系必须 PRESERVE：移除检查任务是日常操作，"
            "不得连带物理删除不符合项 / 证据 / 现场检查记录。"
        )


def test_cascade_depth_guard_is_bounded():
    """级联展开必须有层数上限 —— 防御环状关系导致无限循环。"""
    from app.utils.soft_delete import MAX_CASCADE_DEPTH, _child_table

    assert 2 <= MAX_CASCADE_DEPTH <= 20, (
        f"MAX_CASCADE_DEPTH={MAX_CASCADE_DEPTH} 不合理："
        "太小会漏掉多层归属（项目→计划项→区域记录），太大则失去防御意义"
    )
    assert _child_table("audit_projects"), (
        "audit_projects 应至少有一条需级联的子关系，否则级联机制形同虚设"
    )
    assert _child_table("template_items"), (
        "template_items 需要自引用级联（分类 → 子分类 → 检查项），否则孙节点"
        "会因父节点软删而从 build_tree 中整体消失"
    )


def test_project_sibling_cascades_delete_fk_dependents_first():
    """区域记录必须排在其引用的区域之前删除，防止 FK 23503。"""
    from app.utils.soft_delete import _child_table, _order_cascade_relations

    metadata = _metadata()
    ordered = _order_cascade_relations(
        _child_table("audit_projects"), metadata.tables
    )
    names = [name for name, _column, _policy in ordered]

    assert names.index("audit_area_records") < names.index("audit_areas")


def test_soft_cascade_targets_have_deleted_at_column():
    """CASCADE_SOFT 的目标表必须同时具备 is_deleted 与 deleted_at。

    缺 deleted_at 时批量 UPDATE 无法写入删除时间，会产生"删了但没有删除时间戳"
    的半残状态 —— 恢复流程和审计日志都依赖这个字段。
    """
    from app.utils.soft_delete import CASCADE_SOFT, FK_CASCADE_POLICY

    metadata = _metadata()
    problems: list[str] = []

    for (child_table, _col, _parent), (policy, _) in FK_CASCADE_POLICY.items():
        if policy != CASCADE_SOFT:
            continue
        table = metadata.tables.get(child_table)
        if table is None:
            continue
        if "deleted_at" not in table.columns:
            problems.append(f"{child_table} 缺 deleted_at 列")

    assert not problems, (
        "以下表登记了 CASCADE_SOFT 但缺少 deleted_at 列：\n"
        + "\n".join(f"  {p}" for p in sorted(set(problems)))
    )


def test_hard_cascade_only_used_on_tables_without_soft_delete():
    """CASCADE_HARD 只允许用于**没有 is_deleted 列**的表。

    对有软删能力的表使用硬删是不可逆的过度操作 —— 本可恢复的数据被永久销毁。
    """
    from app.utils.soft_delete import CASCADE_HARD, FK_CASCADE_POLICY

    soft_tables = _soft_deletable_tables()
    offenders = [
        f"{c}.{col} → {p}"
        for (c, col, p), (policy, _) in FK_CASCADE_POLICY.items()
        if policy == CASCADE_HARD and c in soft_tables
    ]

    assert not offenders, (
        "以下表支持软删除，却对子行使用了不可逆的 CASCADE_HARD：\n"
        + "\n".join(f"  {o}" for o in offenders)
        + "\n\n请改用 CASCADE_SOFT，保留可恢复性。"
    )


def test_soft_cascade_only_used_on_tables_with_soft_delete():
    """反之，CASCADE_SOFT 只能用于有 is_deleted 列的表，否则 SQL 会报字段不存在。"""
    from app.utils.soft_delete import CASCADE_SOFT, FK_CASCADE_POLICY

    soft_tables = _soft_deletable_tables()
    offenders = [
        f"{c}.{col} → {p}"
        for (c, col, p), (policy, _) in FK_CASCADE_POLICY.items()
        if policy == CASCADE_SOFT and c not in soft_tables
    ]

    assert not offenders, (
        "以下表没有 is_deleted 列，却登记了 CASCADE_SOFT（执行时会报错）：\n"
        + "\n".join(f"  {o}" for o in offenders)
    )


def test_cascade_targets_actually_exist_in_metadata():
    """策略表里引用的表和列必须真实存在 —— 防止拼写错误导致级联静默失效。"""
    metadata = _metadata()
    problems: list[str] = []

    for child_table, child_column, parent_table in _registered_relations():
        table = metadata.tables.get(child_table)
        if table is None:
            problems.append(f"表不存在：{child_table}")
            continue
        if child_column not in table.columns:
            problems.append(f"列不存在：{child_table}.{child_column}")
        if parent_table not in metadata.tables:
            problems.append(f"父表不存在：{parent_table}")

    assert not problems, "策略表引用了不存在的表或列：\n" + "\n".join(
        f"  {p}" for p in sorted(set(problems))
    )


def test_policy_index_matches_policy_table():
    """策略索引与策略表必须一致 —— 两处漂移会让查询到错误的策略。"""
    from app.utils.soft_delete import FK_CASCADE_POLICY, policy_for

    for (child_table, child_column, parent_table), (policy, _reason) in FK_CASCADE_POLICY.items():
        resolved, _ = policy_for(child_table, child_column, parent_table)
        assert resolved == policy, (
            f"{child_table}.{child_column} → {parent_table} 索引返回 {resolved}，"
            f"策略表登记为 {policy}"
        )


def test_same_child_column_never_maps_to_two_parents_with_conflicting_policy():
    """同一个子列若指向多个父表，策略不得互相冲突（索引按列名建，会互相覆盖）。"""
    from app.utils.soft_delete import FK_CASCADE_POLICY

    by_column: dict[tuple[str, str], set[str]] = {}
    for (child_table, child_column, _parent), (policy, _reason) in FK_CASCADE_POLICY.items():
        by_column.setdefault((child_table, child_column), set()).add(policy)

    conflicts = {
        key: policies for key, policies in by_column.items() if len(policies) > 1
    }
    assert not conflicts, (
        "同一子列登记了互相冲突的策略，策略索引会取到任意一个：\n"
        + "\n".join(f"  {k}: {sorted(v)}" for k, v in conflicts.items())
    )


# ---------------------------------------------------------------------------
# 间接级联 —— 外键不在目标表上，FK 图表达不了的归属关系
# ---------------------------------------------------------------------------


def test_deleting_project_must_clean_up_its_inspection_tasks():
    """**回归护栏**：删除审核项目必须一并处理它派生的检查任务。

    这条规则在 FK 图上**不存在** —— 外键是 ``audit_plan_items.inspection_task_id``，
    检查任务反而是计划项的父表。但 ``create_plan_item`` 会自动创建检查任务，
    项目删除后任务仍留在审核员的「我的任务」列表里
    （``tasks.py`` 只过滤 ``InspectionTask.is_deleted``，不看项目是否已删），
    且因计划项已软删而回填不到 ``audit_project_id`` / ``area_name``，
    卡片失去全部上下文。必须显式登记在 ``INDIRECT_CASCADE_POLICY``。
    """
    from app.utils.soft_delete import CASCADE_SOFT, INDIRECT_CASCADE_POLICY

    key = ("audit_projects", "audit_plan_items", "project_id")
    assert key in INDIRECT_CASCADE_POLICY, (
        "缺少「删除审核项目 → 处理其检查任务」的间接级联登记。\n"
        "外键在 audit_plan_items 一侧，information_schema 推导不出来，必须显式声明。"
    )

    via_fk, target_table, policy, reason = INDIRECT_CASCADE_POLICY[key]
    assert via_fk == "inspection_task_id", f"经由列应为 inspection_task_id，实际 {via_fk}"
    assert target_table == "inspection_tasks", f"目标表应为 inspection_tasks，实际 {target_table}"
    assert policy == CASCADE_SOFT, (
        f"应为 {CASCADE_SOFT}（可逆，与计划项状态一致），实际 {policy}"
    )
    assert len(reason.strip()) >= 10, "必须写清楚为什么级联"


def test_indirect_cascade_references_real_tables_and_columns():
    """间接级联引用的表与列必须真实存在 —— 拼错会静默失效，级联形同虚设。"""
    from app.utils.soft_delete import INDIRECT_CASCADE_POLICY

    metadata = _metadata()
    problems: list[str] = []

    for (parent_table, via_table_name, via_parent_column), (
        via_fk_column,
        target_table_name,
        _policy,
        _reason,
    ) in INDIRECT_CASCADE_POLICY.items():
        for name in (parent_table, via_table_name, target_table_name):
            if name not in metadata.tables:
                problems.append(f"表不存在：{name}")

        via = metadata.tables.get(via_table_name)
        if via is not None:
            for column in (via_parent_column, via_fk_column):
                if column not in via.columns:
                    problems.append(f"列不存在：{via_table_name}.{column}")

        target = metadata.tables.get(target_table_name)
        if target is not None and "id" not in target.columns:
            problems.append(f"目标表缺少 id 列：{target_table_name}")

    assert not problems, (
        "间接级联策略引用了不存在的表或列：\n"
        + "\n".join(f"  {p}" for p in sorted(set(problems)))
    )
