"""审核计划项「活动类型」的共享判定。

审核计划项分两类：

* **会议类**（首次/末次会议、内部沟通）—— 不开展现场检查，天然不需要检查模板；
* **检查类**（正常审核、夜间巡视）—— 必须锁定检查模板。

后者缺模板会导致现场检查加载不出检查项（空白项），因此模板在前端表单、
API Schema、Agent 工具三层都被强制为必填。这里集中维护判定逻辑，
避免「会议豁免」的名单在多处各写一份、改一处漏一处。
"""

#: 纯会议活动：不产生现场检查内容，豁免「必须选择检查模板」的约束。
MEETING_ACTIVITY_TYPES = frozenset(
    {"opening_meeting", "closing_meeting", "internal_meeting"}
)


def is_meeting_activity(activity_type: str | None) -> bool:
    """判断计划项是否为纯会议活动（会议类豁免检查模板）。"""
    return str(activity_type or "normal") in MEETING_ACTIVITY_TYPES


def requires_template(activity_type: str | None) -> bool:
    """判断计划项是否必须绑定检查模板（会议类不需要）。"""
    return not is_meeting_activity(activity_type)
