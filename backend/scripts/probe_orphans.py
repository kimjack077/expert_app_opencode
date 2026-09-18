"""只读探查：软删除级联缺失与悬空外键的实际形态。

用于设计清理方案，本身不修改任何数据。全程 ``readonly=True``。

    python scripts/probe_orphans.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2  # noqa: E402

from app.config import settings  # noqa: E402

# (编号, 说明, 计数 SQL, 明细 SQL)
PROBES = [
    (
        "B3",
        "检查记录的 template_id 为空或指向不存在的模板（生成报告会失败）",
        """SELECT count(*) FROM inspection_records r
           WHERE r.is_deleted = false
             AND (r.template_id IS NULL
                  OR NOT EXISTS (SELECT 1 FROM inspection_templates t WHERE t.id = r.template_id))""",
        """SELECT r.id, r.status, r.enterprise_name, r.template_id, r.created_at
           FROM inspection_records r
           WHERE r.is_deleted = false
             AND (r.template_id IS NULL
                  OR NOT EXISTS (SELECT 1 FROM inspection_templates t WHERE t.id = r.template_id))
           ORDER BY r.created_at DESC LIMIT 20""",
    ),
    (
        "B3b",
        "上述记录中已提交（会被使用者真实打开）的条数",
        """SELECT count(*) FROM inspection_records r
           WHERE r.is_deleted = false AND r.status = 'submitted'
             AND (r.template_id IS NULL
                  OR NOT EXISTS (SELECT 1 FROM inspection_templates t WHERE t.id = r.template_id))""",
        """SELECT r.id, r.status, r.enterprise_name, r.created_at
           FROM inspection_records r
           WHERE r.is_deleted = false AND r.status = 'submitted'
             AND (r.template_id IS NULL
                  OR NOT EXISTS (SELECT 1 FROM inspection_templates t WHERE t.id = r.template_id))
           LIMIT 20""",
    ),
    (
        "A1",
        "检查明细挂在已软删的记录上（inspection_record_items 是硬删除表，无 is_deleted 列）",
        """SELECT count(*) FROM inspection_record_items i
           JOIN inspection_records r ON r.id = i.record_id
           WHERE r.is_deleted = true""",
        """SELECT r.id AS record_id, r.status, r.enterprise_name,
                  count(i.id) AS leftover_items
           FROM inspection_records r
           JOIN inspection_record_items i ON i.record_id = r.id
           WHERE r.is_deleted = true
           GROUP BY r.id, r.status, r.enterprise_name
           ORDER BY leftover_items DESC LIMIT 20""",
    ),
    (
        "A2",
        "未删除的检查项挂在已软删的模板上",
        """SELECT count(*) FROM template_items ti
           JOIN inspection_templates t ON t.id = ti.template_id
           WHERE t.is_deleted = true AND ti.is_deleted = false""",
        """SELECT t.id AS template_id, t.name, count(ti.id) AS live_items
           FROM inspection_templates t
           JOIN template_items ti ON ti.template_id = t.id
           WHERE t.is_deleted = true AND ti.is_deleted = false
           GROUP BY t.id, t.name
           ORDER BY live_items DESC LIMIT 20""",
    ),
    (
        "A3",
        "未删除的审核计划项挂在已软删的项目上",
        """SELECT count(*) FROM audit_plan_items p
           JOIN audit_projects pr ON pr.id = p.project_id
           WHERE pr.is_deleted = true AND p.is_deleted = false""",
        """SELECT pr.id AS project_id, pr.title, count(p.id) AS live_items
           FROM audit_projects pr
           JOIN audit_plan_items p ON p.project_id = pr.id
           WHERE pr.is_deleted = true AND p.is_deleted = false
           GROUP BY pr.id, pr.title
           ORDER BY live_items DESC LIMIT 20""",
    ),
    (
        "A4",
        "未删除的任务挂在已软删的项目上（经计划项关联）",
        """SELECT count(*) FROM inspection_tasks t
           JOIN audit_plan_items p ON p.inspection_task_id = t.id
           JOIN audit_projects pr ON pr.id = p.project_id
           WHERE pr.is_deleted = true AND t.is_deleted = false""",
        """SELECT t.id, t.title, t.status, pr.title AS project_title
           FROM inspection_tasks t
           JOIN audit_plan_items p ON p.inspection_task_id = t.id
           JOIN audit_projects pr ON pr.id = p.project_id
           WHERE pr.is_deleted = true AND t.is_deleted = false
           LIMIT 20""",
    ),
    (
        "A5",
        "未删除的记录关联了已软删的企业",
        """SELECT count(*) FROM inspection_records r
           JOIN enterprises e ON e.id = r.enterprise_id
           WHERE e.is_deleted = true AND r.is_deleted = false""",
        """SELECT r.id, r.status, r.enterprise_name, e.name AS enterprise
           FROM inspection_records r
           JOIN enterprises e ON e.id = r.enterprise_id
           WHERE e.is_deleted = true AND r.is_deleted = false LIMIT 20""",
    ),
    (
        "A6",
        "未删除的记录关联了已软删的模板",
        """SELECT count(*) FROM inspection_records r
           JOIN inspection_templates t ON t.id = r.template_id
           WHERE t.is_deleted = true AND r.is_deleted = false""",
        """SELECT r.id, r.status, t.name AS template, r.created_at
           FROM inspection_records r
           JOIN inspection_templates t ON t.id = r.template_id
           WHERE t.is_deleted = true AND r.is_deleted = false LIMIT 20""",
    ),
]


def main() -> int:
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor()

    for key, title, count_sql, detail_sql in PROBES:
        print("=" * 78)
        print(f"[{key}] {title}")
        print("=" * 78)
        cur.execute(count_sql)
        total = cur.fetchone()[0]
        print(f"命中：{total}\n")
        if total:
            cur.execute(detail_sql)
            columns = [d[0] for d in cur.description]
            print("  " + " | ".join(columns))
            for row in cur.fetchall():
                print("  " + " | ".join(str(v)[:32] for v in row))
        print()

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
