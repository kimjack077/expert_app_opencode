# -*- coding: utf-8 -*-
"""存量脏数据清理脚本（2026-09-15 数据体检报告的执行件）。

清理范围（对应《易审通存量数据体检报告》待决策事项 1 / 2，已经业务确认）：
- A 类：已提交但无总体结论的检查记录
- B 类：已提交但必填检查项未填完的检查记录
- E 类：孤儿附件（record_id / task_id 均为空的 media_files）

处理方式：全部软删除（is_deleted=true + deleted_at），不做物理删除，
保证审计留痕；孤儿附件的物理文件路径会导出到 stdout，由运维在服务器上另行删除。

用法（在 backend/ 下，读本机 .env 连接远程库）：
    python scripts/cleanup_dirty_data.py            # 实际执行
    python scripts/cleanup_dirty_data.py --dry-run  # 只查看将受影响的行
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

import asyncpg
from dotenv import load_dotenv

# A 类：已提交但无总体结论
A_SQL = """
select id, enterprise_name, inspection_date, 'A' as category
from inspection_records
where is_deleted = false and status = 'submitted'
  and (overall_result is null or btrim(overall_result) = '')
"""

# B 类：已提交但必填项没填完（与体检报告同一口径）
B_SQL = """
with leaves as (
    select ti.template_id, ti.id as ti_id
    from template_items ti
    where ti.is_deleted = false and coalesce(ti.is_category, false) = false
      and ti.is_required is not false
      and not exists (select 1 from template_items c
                      where c.parent_id = ti.id and c.is_deleted = false)
)
select r.id, r.enterprise_name, r.inspection_date, 'B' as category
from inspection_records r
join leaves l on l.template_id = r.template_id
left join inspection_record_items ri
       on ri.record_id = r.id and ri.template_item_id = l.ti_id
where r.is_deleted = false and r.status = 'submitted'
group by r.id, r.enterprise_name, r.inspection_date
having count(distinct ri.template_item_id) filter (
           where coalesce(ri.radio_value,'') <> '' or coalesce(ri.result,'') <> ''
              or coalesce(ri.numeric_value,'') <> '' or coalesce(ri.score_value,'') <> ''
              or coalesce(ri.text_value,'') <> ''
       ) < count(distinct l.ti_id)
"""

# E 类：孤儿附件
E_SQL = """
select id, file_path, uploaded_at
from media_files
where is_deleted = false and record_id is null and task_id is null
"""


async def main(dry_run: bool) -> None:
    load_dotenv()
    conn = await asyncpg.connect(
        host=os.getenv("PG_HOST"),
        port=int(os.getenv("PG_PORT", "5432")),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        database=os.getenv("PG_DB"),
    )
    try:
        dirty = {r["id"]: r for r in (await conn.fetch(A_SQL)) + (await conn.fetch(B_SQL))}
        orphans = await conn.fetch(E_SQL)

        print(f"== A/B 类脏记录（去重后 {len(dirty)} 条） ==")
        for r in sorted(dirty.values(), key=lambda x: str(x["id"])):
            print(f"  [{r['category']}] {r['id']} | {r['enterprise_name']} | {r['inspection_date']}")
        print(f"== E 类孤儿附件（{len(orphans)} 条） ==")
        for m in orphans:
            print(f"  {m['id']} | {m['file_path']} | {m['uploaded_at']}")

        if dry_run:
            print("\n[dry-run] 未做任何修改。")
            return

        now = datetime.now(timezone.utc)
        async with conn.transaction():
            if dirty:
                await conn.execute(
                    """
                    update inspection_records
                    set is_deleted = true, deleted_at = $1
                    where id = any($2::uuid[]) and is_deleted = false
                    """,
                    now,
                    list(dirty.keys()),
                )
            if orphans:
                await conn.execute(
                    """
                    update media_files
                    set is_deleted = true, deleted_at = $1
                    where id = any($2::uuid[]) and is_deleted = false
                    """,
                    now,
                    [m["id"] for m in orphans],
                )

        print(f"\n[done] 软删除完成：检查记录 {len(dirty)} 条，孤儿附件 {len(orphans)} 条")
        print("以下物理文件已在库中解除引用，可在服务器 backend/uploads 下删除：")
        for m in orphans:
            print(f"  {m['file_path']}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main(dry_run="--dry-run" in sys.argv))
