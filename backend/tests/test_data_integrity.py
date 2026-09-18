"""数据完整性门禁：零容忍检查项。

═══════════════════════════════════════════════════════════════════════════
 设计思路
═══════════════════════════════════════════════════════════════════════════
`scripts/db_health_check.py` 会扫描 24 项数据一致性检查，其中一部分属于
**存量债务**（如已软删父记录下的孤儿明细），短时间内无法清零，适合放在
体检报告里人工跟踪。

而另一部分属于**绝对不允许出现**的结构性错误——一旦出现，用户一定会
看到错误结果（报告失败、页面 404、编号重复）。这类检查项在此固化为
测试，断言必须为 0，纳入回归门禁。

与 `db_health_check.py` 的分工：

    体检脚本 → 全量 24 项，输出报告，跟踪存量债务趋势
    本测试   → 零容忍项，断言为 0，防止新增

运行前提：`EFIS_TEST_DB_NAME=db_expert_test`（见 conftest.py）。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.api

# 零容忍检查项：(编号, 说明, SQL)
# SQL 均只读，返回单个计数。
ZERO_TOLERANCE = [
    (
        "D1",
        "检查结论出现非法枚举值",
        """SELECT count(*) FROM inspection_record_items
           WHERE radio_value IS NOT NULL AND radio_value <> ''
             AND lower(trim(radio_value)) NOT IN (
               'pass','fail','na','not_applicable','not-applicable','n/a',
               'compliant','qualified','non_compliant','unqualified',
               'pending_rectification','observe'
             )""",
        "前端映射表查不到该值 → 页面显示英文原文或空白",
    ),
    (
        "C1",
        "检查项的父节点不存在（模板树断裂）",
        """SELECT count(*) FROM template_items c
           LEFT JOIN template_items p ON p.id = c.parent_id
           WHERE c.parent_id IS NOT NULL AND p.id IS NULL""",
        "树渲染时该节点及其子树整体丢失，表现为「条目消失」",
    ),
    (
        "C2",
        "检查项的父节点属于另一个模板",
        """SELECT count(*) FROM template_items c
           JOIN template_items p ON p.id = c.parent_id
           WHERE c.template_id <> p.template_id""",
        "模板条目数量统计错乱",
    ),
    (
        "C3",
        "模板树存在自引用（parent_id = id）",
        "SELECT count(*) FROM template_items WHERE parent_id = id",
        "递归构建树时死循环",
    ),
    (
        "B2",
        "记录的企业 ID 指向不存在的企业",
        """SELECT count(*) FROM inspection_records r
           LEFT JOIN enterprises e ON e.id = r.enterprise_id
           WHERE r.enterprise_id IS NOT NULL AND e.id IS NULL""",
        "详情页取企业信息必然失败",
    ),
    (
        "B3",
        "记录引用了不存在的模板",
        """SELECT count(*) FROM inspection_records r
           LEFT JOIN inspection_templates t ON t.id = r.template_id
           WHERE t.id IS NULL""",
        "报告无法装配检查项 → 生成报告失败或空白",
    ),
    (
        "B4",
        "计划项引用了不存在的检查任务",
        """SELECT count(*) FROM audit_plan_items p
           LEFT JOIN inspection_tasks t ON t.id = p.inspection_task_id
           WHERE p.inspection_task_id IS NOT NULL AND t.id IS NULL""",
        "任务列表与项目计划对不上",
    ),
    (
        "A7",
        "软删除标记与删除时间不一致",
        """SELECT
             (SELECT count(*) FROM inspection_records WHERE is_deleted = true AND deleted_at IS NULL)
           + (SELECT count(*) FROM inspection_templates WHERE is_deleted = true AND deleted_at IS NULL)
           + (SELECT count(*) FROM enterprises WHERE is_deleted = true AND deleted_at IS NULL)
           + (SELECT count(*) FROM audit_projects WHERE is_deleted = true AND deleted_at IS NULL)
           + (SELECT count(*) FROM inspection_tasks WHERE is_deleted = true AND deleted_at IS NULL)""",
        "审计追溯无法确定删除时间",
    ),
    (
        "E1",
        "已提交的记录没有任何检查明细",
        """SELECT count(*) FROM inspection_records r
           WHERE r.is_deleted = false AND r.status = 'submitted'
             AND NOT EXISTS (SELECT 1 FROM inspection_record_items i WHERE i.record_id = r.id)""",
        "报告空白、统计全 0，用户会认为数据丢失",
    ),
    (
        "F1",
        "未删除的模板存在重复编码",
        """SELECT count(*) FROM (
             SELECT code FROM inspection_templates
             WHERE is_deleted = false AND code IS NOT NULL AND code <> ''
             GROUP BY code HAVING count(*) > 1
           ) x""",
        "新建模板报「编码已存在」，列表却只看到一条",
    ),
    (
        "F2",
        "未删除的任务存在重复编号",
        """SELECT count(*) FROM (
             SELECT task_no FROM inspection_tasks
             WHERE is_deleted = false AND task_no IS NOT NULL
             GROUP BY task_no HAVING count(*) > 1
           ) x""",
        "任务编号是业务凭证号，重复导致对账困难",
    ),
    (
        "F3",
        "未删除的企业存在重复统一社会信用代码",
        """SELECT count(*) FROM (
             SELECT credit_code FROM enterprises
             WHERE is_deleted = false AND credit_code IS NOT NULL AND credit_code <> ''
             GROUP BY credit_code HAVING count(*) > 1
           ) x""",
        "同一家企业重复建档，审核记录分散",
    ),
]


@pytest.fixture(scope="module")
def db_conn():
    """测试库只读连接。"""
    import psycopg2

    from app.config import settings

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    conn.set_session(readonly=True, autocommit=True)
    yield conn
    conn.close()


# 存量债务基线：这些检查项当前不为 0，但**不允许继续恶化**。
# 每清理一条就把基线调小；清零后请从本字典删除，让零容忍断言接管。
BASELINE = {
    # 4 条记录引用了已不存在的模板（2026-09-17 体检发现）。
    # 影响：生成报告时无法装配检查项。建议清理或补建模板。
    "B3": 4,
}


@pytest.mark.parametrize(
    "key,title,sql,impact",
    ZERO_TOLERANCE,
    ids=[c[0] for c in ZERO_TOLERANCE],
)
def test_zero_tolerance_data_integrity(db_conn, key, title, sql, impact):
    """结构性数据错误必须为 0——出现即说明写入链路或删除逻辑存在缺陷。"""
    cur = db_conn.cursor()
    cur.execute(sql)
    count = int(cur.fetchone()[0] or 0)

    allowed = BASELINE.get(key, 0)

    if allowed:
        assert count <= allowed, (
            f"[{key}] {title}：命中 {count} 条，超过存量基线 {allowed} 条——**有新增**。\n"
            f"影响：{impact}\n"
            "请先运行 scripts/db_health_check.py 定位新增来源。"
        )
        return

    assert count == 0, (
        f"[{key}] {title}：命中 {count} 条。\n"
        f"影响：{impact}\n"
        "请先运行 scripts/db_health_check.py 查看样例数据，"
        "确认是存量数据问题还是新引入的缺陷。"
    )
