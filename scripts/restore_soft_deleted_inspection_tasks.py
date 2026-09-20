# -*- coding: utf-8 -*-
"""还原被误软删的 inspection_tasks（演示主线的 H5 现场检查依赖它）。

背景（2026-09-20 复验发现）：
  * inspection_tasks 共 116 行，**全部** is_deleted=true，有效行为 0；
  * 其中 23 行删除时间为 2026-09-20 02:00~02:21 UTC（本地 10:00~10:21），
    系上一轮清理动作所致；
  * 但 31 条未删除的 audit_plan_items 仍把 inspection_task_id 指向这些已删任务，
    且演示任务 edd9c5e7（特种装备现场质量安全专项检查（客户演示））同样被删；
  * 后果：H5 /audit-tasks → /inspection/:id 的 getTask() 恒 404，现场检查页
    显示「检查记录不存在」，演示第六幕不可执行。

软删除同时把唯一字段 task_no 改写成 ``<原值>_deleted_<epoch>``，还原时需剥掉后缀。

还原范围（保守）：
  1) 被未删除计划项引用的任务；
  2) docs/_new_demo_assets.json 中的演示任务。
不触碰其它历史删除记录。

用法：
    python ../_verify/restore_inspection_tasks_20260920.py          # 预演
    python ../_verify/restore_inspection_tasks_20260920.py --apply  # 执行
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.getcwd())  # 需在 backend/ 目录下运行

from sqlalchemy import text  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402

DEMO_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "_new_demo_assets.json")

TARGET_SQL = """
WITH targets AS (
    SELECT DISTINCT p.inspection_task_id AS id
    FROM audit_plan_items p
    WHERE p.is_deleted = false AND p.inspection_task_id IS NOT NULL
    UNION
    SELECT CAST(:demo_id AS uuid)
)
SELECT t.id, t.task_no, t.status, t.deleted_at
FROM inspection_tasks t
JOIN targets ON targets.id = t.id
WHERE t.is_deleted = true
ORDER BY t.task_no
"""

RESTORE_SQL = """
WITH targets AS (
    SELECT DISTINCT p.inspection_task_id AS id
    FROM audit_plan_items p
    WHERE p.is_deleted = false AND p.inspection_task_id IS NOT NULL
    UNION
    SELECT CAST(:demo_id AS uuid)
)
UPDATE inspection_tasks t
SET is_deleted = false,
    deleted_at = NULL,
    task_no = regexp_replace(t.task_no, '_deleted_[0-9]+$', '')
FROM targets
WHERE t.id = targets.id AND t.is_deleted = true
"""


async def main(apply: bool) -> int:
    with open(os.path.abspath(DEMO_ASSETS), encoding="utf-8") as fh:
        demo_id = json.load(fh)["task_id"]
    print(f"演示任务 id = {demo_id}")

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text(TARGET_SQL), {"demo_id": demo_id})).fetchall()
        print(f"待还原任务 = {len(rows)} 条")
        for r in rows[:8]:
            print("   ", r[0], r[1], r[2], r[3])
        if len(rows) > 8:
            print(f"    ... 其余 {len(rows) - 8} 条略")

        # 唯一键冲突预检
        dup = (await db.execute(text("""
            SELECT regexp_replace(task_no, '_deleted_[0-9]+$', '') AS base, count(*)
            FROM inspection_tasks
            WHERE id IN (SELECT id FROM inspection_tasks WHERE is_deleted = true)
            GROUP BY 1 HAVING count(*) > 1
        """))).fetchall()
        print(f"还原后 task_no 潜在重名 = {len(dup)} 组（应为 0）")
        if dup:
            print("   冲突：", dup[:5])
            return 3

        if not apply:
            print("预演结束，未修改任何数据。加 --apply 执行。")
            return 0

        res = await db.execute(text(RESTORE_SQL), {"demo_id": demo_id})
        await db.commit()
        print(f"已还原 {res.rowcount} 条 inspection_tasks")

        left = (await db.execute(text("SELECT count(*) FROM inspection_tasks WHERE is_deleted = true"))).scalar()
        active = (await db.execute(text("SELECT count(*) FROM inspection_tasks WHERE is_deleted = false"))).scalar()
        print(f"还原后：有效 {active} 条 / 仍软删 {left} 条")
        broken = (await db.execute(text("""
            SELECT count(*) FROM audit_plan_items p
            JOIN inspection_tasks t ON t.id = p.inspection_task_id
            WHERE p.is_deleted = false AND t.is_deleted = true
        """))).scalar()
        print(f"仍指向已删任务的有效计划项 = {broken}（应为 0）")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main("--apply" in sys.argv)))
