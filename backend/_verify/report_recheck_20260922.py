"""只读复核测试报告中的数据类结论（全部 SELECT，不写库）。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from app.config import settings  # noqa: E402

QUERIES = [
    ("污染邮箱（email 含 _deleted_ 或 +deleted）",
     "SELECT count(*) FROM users WHERE email LIKE '%_deleted_%' OR email LIKE '%+deleted%'"),
    ("软删且仍启用的用户",
     "SELECT count(*) FROM users WHERE is_deleted=true AND is_active=true"),
    ("软删用户的 email 样本（验证新改名格式）",
     "SELECT email FROM users WHERE is_deleted=true AND email IS NOT NULL LIMIT 5"),
    ("孤儿计划项（父项目已软删）",
     "SELECT count(*) FROM audit_plan_items p JOIN audit_projects pr ON p.project_id=pr.id "
     "WHERE pr.is_deleted=true AND p.is_deleted=false"),
    ("孤儿组员（父项目已软删）",
     "SELECT count(*) FROM audit_team_members m JOIN audit_projects pr ON m.project_id=pr.id "
     "WHERE pr.is_deleted=true AND m.is_deleted=false"),
    ("孤儿记录明细（父记录已软删）",
     "SELECT count(*) FROM inspection_record_items i JOIN inspection_records r ON i.record_id=r.id "
     "WHERE r.is_deleted=true AND i.is_deleted=false"),
    ("bak 备份表数量",
     "SELECT count(*) FROM information_schema.tables WHERE table_name LIKE '%bak%' AND table_schema='public'"),
    ("软删模板 c742a65e 的状态",
     "SELECT id, name, is_deleted, deleted_at FROM inspection_templates WHERE id::text LIKE 'c742a65e%'"),
    ("引用该模板的有效任务",
     "SELECT t.task_no, t.is_deleted, t.status, t.assigned_to FROM inspection_tasks t "
     "JOIN inspection_templates tp ON t.template_id=tp.id "
     "WHERE tp.id::text LIKE 'c742a65e%' AND t.is_deleted=false"),
    ("有效用户清单（角色分布）",
     "SELECT role, count(*) FROM users WHERE is_deleted=false AND is_active=true GROUP BY role"),
]


async def main() -> None:
    conn = await asyncpg.connect(
        host=settings.effective_pg_host,
        port=settings.PG_PORT,
        user=settings.PG_USER,
        password=settings.PG_PASSWORD,
        database=settings.PG_DB,
    )
    for label, sql in QUERIES:
        try:
            rows = await conn.fetch(sql)
            print(f"[{label}]")
            for r in rows:
                print("   ", dict(r))
            if not rows:
                print("    (0 rows)")
        except Exception as exc:
            print(f"[{label}] ERROR: {exc}")
    await conn.close()


asyncio.run(main())
