# -*- coding: utf-8 -*-
"""存量「无检查模板」审核计划项清理脚本（2026-10-12）。

背景：Agent 生成审核计划时，部分计划项没有锁定检查模板，现场执行时是空白检查项。
现在规则收紧为「检查类活动必须绑定检查模板」，因此历史遗留的无模板计划项属于脏数据。

清理范围（业务已确认「全部无模板都删」）：
- 所有 ``is_deleted = false 且 template_id is null`` 的 ``audit_plan_items``
  （含会议类；会议类在新规则下虽可豁免，但为保持库内一致一并清理，且为软删可恢复）。

处理方式：复用与 ``delete_plan_item`` 完全相同的级联路径
（``app.utils.soft_delete.soft_delete_cascade``），保证口径一致：
- 先软删关联的检查任务（``inspection_tasks``，连带其硬删除的 ``task_item_records``）；
- 再软删计划项自身（连带可重生成的 ``ai_draft_records``）；
- ``audit_area_records`` / ``evidence_submissions`` / ``nonconformities`` 按策略
  **有意保留**（现场结论与证据不因移除计划项而销毁）。

全部为软删除，可通过 ``is_deleted`` 复位恢复。

用法（在 backend/ 下，读本机 .env 连接远程共享库）：
    python scripts/cleanup_no_template_plan_items.py            # 实际执行
    python scripts/cleanup_no_template_plan_items.py --dry-run  # 只查看将受影响的行
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select

# 允许 `python scripts/cleanup_no_template_plan_items.py` 从 backend/ 运行。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import AsyncSessionLocal  # noqa: E402
from app.models.audit_project import AuditPlanItem  # noqa: E402
from app.models.task import InspectionTask  # noqa: E402
from app.utils.activity import is_meeting_activity  # noqa: E402
from app.utils.soft_delete import soft_delete_cascade  # noqa: E402


async def main(dry_run: bool) -> None:
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AuditPlanItem)
            .where(
                AuditPlanItem.is_deleted == False,  # noqa: E712
                AuditPlanItem.template_id.is_(None),
            )
            .order_by(AuditPlanItem.plan_date, AuditPlanItem.area_name)
        )
        plan_items = list(result.scalars().all())

        print(f"== 无检查模板的审核计划项：{len(plan_items)} 条 ==")
        meeting_cnt = 0
        task_cnt = 0
        for it in plan_items:
            is_meeting = is_meeting_activity(it.activity_type)
            meeting_cnt += int(is_meeting)
            task_cnt += int(it.inspection_task_id is not None)
            tag = "会议" if is_meeting else "检查"
            print(
                f"  [{tag}] {it.id} | {it.plan_date} | {it.area_name} | "
                f"activity_type={it.activity_type} | status={it.status} | "
                f"task={str(it.inspection_task_id)[:8] if it.inspection_task_id else '-'}"
            )
        print(
            f"\n其中：会议类 {meeting_cnt} 条，检查类 {len(plan_items) - meeting_cnt} 条；"
            f"带检查任务 {task_cnt} 条。"
        )

        if dry_run:
            print("\n[dry-run] 未做任何修改。")
            return

        affected: dict[str, int] = {}
        for it in plan_items:
            # 先删关联检查任务（含其硬删除的 task_item_records），与 delete_plan_item 同序
            if it.inspection_task_id:
                task = await db.get(InspectionTask, it.inspection_task_id)
                if task and not task.is_deleted:
                    for table_name, count in (
                        await soft_delete_cascade(db, task, unique_fields=["task_no"])
                    ).items():
                        affected[table_name] = affected.get(table_name, 0) + count
            # 再删计划项本身
            for table_name, count in (await soft_delete_cascade(db, it)).items():
                affected[table_name] = affected.get(table_name, 0) + count

        await db.commit()

        print(f"\n[done] 已软删除 {len(plan_items)} 条无模板计划项。级联明细：")
        if affected:
            for table_name, count in sorted(affected.items()):
                print(f"  {table_name}: {count}")
        else:
            print("  （无级联子表受影响）")
        print("提示：全部为软删除，如需恢复可将对应行 is_deleted 复位为 false。")


if __name__ == "__main__":
    asyncio.run(main(dry_run="--dry-run" in sys.argv))
