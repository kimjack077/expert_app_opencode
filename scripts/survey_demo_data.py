"""演示数据补齐前的现状勘察（只读，不写任何数据）。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import psycopg2  # noqa: E402
from app.config import settings  # noqa: E402

TEST_ENTERPRISES = [
    "API测试企业-CRUD",
    "测试企业_1784265654",
    "测试企业_直接测试",
    "测试科技有限公司-已编辑",
    "AI_NATIVE_山东盛发焦化模拟企业",
]

TEST_USERS = ["test_auditor_new", "test_crud_user", "testuser", "test_auditor"]

DEMO_PROJECT = "dd000795-57ba-44ef-9eb3-7dec39818b1f"
TEMPLATE_QUALITY = "4f72edfe-6223-4392-8cbb-6761f586d261"
EXPERT_ID = "4d7549ee-e8a9-4c85-be45-08a8b7635e01"


def main() -> int:
    conn = psycopg2.connect(
        host=settings.PG_HOST,
        port=settings.PG_PORT,
        dbname=settings.PG_DB,
        user=settings.PG_USER,
        password=settings.PG_PASSWORD,
    )
    cur = conn.cursor()
    print(f"库：{settings.PG_HOST}/{settings.PG_DB}\n")

    print("=" * 78)
    print("一、测试企业引用关系（决定能否安全软删）")
    print("=" * 78)
    for name in TEST_ENTERPRISES:
        cur.execute(
            "SELECT id FROM enterprises WHERE name=%s AND is_deleted=false", (name,)
        )
        row = cur.fetchone()
        if not row:
            print(f"  {name:32s} 未找到")
            continue
        eid = row[0]
        stats = {}
        for label, sql in (
            ("项目", "SELECT count(*) FROM audit_projects WHERE enterprise_id=%s AND is_deleted=false"),
            ("记录", "SELECT count(*) FROM inspection_records WHERE enterprise_id=%s AND is_deleted=false"),
            ("资质", "SELECT count(*) FROM enterprise_qualifications WHERE enterprise_id=%s"),
            ("产品", "SELECT count(*) FROM enterprise_products WHERE enterprise_id=%s"),
        ):
            cur.execute(sql, (eid,))
            stats[label] = cur.fetchone()[0]
        cur.execute(
            "SELECT title FROM audit_projects WHERE enterprise_id=%s AND is_deleted=false",
            (eid,),
        )
        titles = [r[0] for r in cur.fetchall()]
        print(
            f"  {name:32s} 项目={stats['项目']} 记录={stats['记录']} "
            f"资质={stats['资质']} 产品={stats['产品']}"
        )
        for t in titles:
            print(f"       └ 项目：{t[:70]}")

    print()
    print("=" * 78)
    print("二、测试账号的业务足迹（决定「删」还是「停用」）")
    print("=" * 78)
    for username in TEST_USERS:
        cur.execute(
            "SELECT id, full_name, role, is_active FROM users WHERE username=%s AND is_deleted=false",
            (username,),
        )
        row = cur.fetchone()
        if not row:
            print(f"  {username:20s} 未找到")
            continue
        uid, full_name, role, is_active = row
        cur.execute(
            "SELECT count(*) FROM inspection_tasks WHERE assigned_to=%s AND is_deleted=false",
            (uid,),
        )
        tasks = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM audit_team_members WHERE member_id=%s AND is_deleted=false",
            (uid,),
        )
        teams = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM audit_plan_items WHERE %s = ANY(assigned_member_ids) AND is_deleted=false",
            (uid,),
        )
        plans = cur.fetchone()[0]
        print(
            f"  {username:20s} {full_name or '':14s} {role:10s} 启用={is_active} "
            f"任务={tasks} 审核组={teams} 计划项={plans}"
        )

    print()
    print("=" * 78)
    print("三、演示项目关键状态")
    print("=" * 78)
    cur.execute(
        "SELECT id, area_name, status, inspection_task_id FROM audit_plan_items "
        "WHERE project_id=%s AND is_deleted=false ORDER BY plan_date",
        (DEMO_PROJECT,),
    )
    for r in cur.fetchall():
        print(f"  计划项 {r[1]:10s} status={r[2]:12s} task={r[3]}")
    cur.execute(
        "SELECT id, title, status, assigned_to FROM inspection_tasks "
        "WHERE audit_project_id=%s AND is_deleted=false",
        (DEMO_PROJECT,),
    )
    for r in cur.fetchall():
        print(f"  任务   {r[1][:44]:46s} status={r[2]:12s} assigned={r[3]}")

    print()
    print("=" * 78)
    print("四、expert 账号当前任务")
    print("=" * 78)
    cur.execute(
        "SELECT id, title, status FROM inspection_tasks "
        "WHERE assigned_to=%s AND is_deleted=false ORDER BY created_at",
        (EXPERT_ID,),
    )
    rows = cur.fetchall()
    print(f"  共 {len(rows)} 条")
    for r in rows:
        print(f"    {r[2]:12s} {r[1][:60]}")

    print()
    print("=" * 78)
    print("五、质量安全测试模板结构（第六幕演示用）")
    print("=" * 78)
    cur.execute(
        "SELECT id, title, is_category, parent_id, result_type, risk_level, is_required "
        "FROM template_items WHERE template_id=%s AND is_deleted=false ORDER BY created_at",
        (TEMPLATE_QUALITY,),
    )
    for r in cur.fetchall():
        kind = "目录" if r[2] else "检查项"
        print(f"  [{kind}] {r[1]:10s} parent={str(r[3])[:8]:9s} type={r[4]} risk={r[5]}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
