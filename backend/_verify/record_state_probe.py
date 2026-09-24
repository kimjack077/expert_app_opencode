"""只读：诊断 /inspection/030a1c08-... 页面的数据状态（record 与 task 两种可能都查）。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from app.config import settings  # noqa: E402

TARGET = "030a1c08-1ea4-44c2-840b-e61a362e065d"


async def main() -> None:
    conn = await asyncpg.connect(
        host=settings.effective_pg_host,
        port=settings.PG_PORT,
        user=settings.PG_USER,
        password=settings.PG_PASSWORD,
        database=settings.PG_DB,
    )

    # ── 作为检查记录 ──────────────────────────────────────────────
    rec = await conn.fetchrow(
        "SELECT id, status, overall_result, is_deleted, inspector_id, template_id, "
        "enterprise_name, inspection_date, created_at, updated_at "
        "FROM inspection_records WHERE id = $1::uuid",
        TARGET,
    )
    print("== 作为 inspection_records ==")
    print("  ", dict(rec) if rec else "NOT FOUND")

    if rec:
        n = await conn.fetchrow(
            "SELECT count(*) AS total, "
            "count(*) FILTER (WHERE result IS NOT NULL OR result_value IS NOT NULL) AS filled "
            "FROM inspection_record_items WHERE record_id = $1::uuid",
            TARGET,
        )
        print("   items:", dict(n))
        for s in await conn.fetch(
            "SELECT id, template_item_id, result, radio_value, result_value, score_value, "
            "numeric_value, text_value FROM inspection_record_items WHERE record_id = $1::uuid LIMIT 6",
            TARGET,
        ):
            print("     ", dict(s))
        tpl = await conn.fetchrow(
            "SELECT id, name, is_deleted FROM inspection_templates WHERE id = $1",
            rec["template_id"],
        )
        print("   template:", dict(tpl) if tpl else None)
        print(
            "   template 有效检查项数:",
            await conn.fetchval(
                "SELECT count(*) FROM template_items WHERE template_id = $1 AND is_deleted = false",
                rec["template_id"],
            ),
        )

    # ── 作为检查任务 ──────────────────────────────────────────────
    task = await conn.fetchrow(
        "SELECT id, task_no, status, is_deleted, assigned_to, template_id, target_name, task_mode "
        "FROM inspection_tasks WHERE id = $1::uuid",
        TARGET,
    )
    print("\n== 作为 inspection_tasks ==")
    print("  ", dict(task) if task else "NOT FOUND")

    if task:
        print(
            "   已填 TaskItemRecord:",
            await conn.fetchval(
                "SELECT count(*) FROM task_item_records WHERE task_id = $1::uuid", TARGET
            ),
        )
        tpl = await conn.fetchrow(
            "SELECT id, name, is_deleted FROM inspection_templates WHERE id = $1",
            task["template_id"],
        )
        print("   template:", dict(tpl) if tpl else None)
        print(
            "   template 有效检查项数:",
            await conn.fetchval(
                "SELECT count(*) FROM template_items WHERE template_id = $1 AND is_deleted = false",
                task["template_id"],
            ),
        )

    print(
        "\n== 两张表都没查到则说明该 id 不存在（前端会报「加载失败」）=="
        if not rec and not task
        else ""
    )
    await conn.close()


asyncio.run(main())
