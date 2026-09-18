"""heal_numeric_verdicts_20260918.py - 存量数值项错误「合格」与空错误信息自愈

对应 2026-09-18 全功能实测：

BUG-11（存量部分）：历史客户端对任何数值录入都默认写 result='pass'，
未配置阈值的数值/打分项因此被虚算进合格数，抬高合规率。本脚本把这些
无阈值依据的 pass 清空（记录本身保留，数值仍在，统计口径归入「其他项」）。
只处理 task_item_records（日常检查任务填报，是默认 pass 的唯一写入源），
判定依据 join template_items 的 check_type/min_value/max_value/pass_score。

BUG-06（存量部分）：修复前失败的成果生成任务 error_message 为空，
用户无法判断失败原因。回填一条可读的历史说明，提示直接重试。

用法::

    python -m scripts.heal_numeric_verdicts_20260918           # 预演（默认）
    python -m scripts.heal_numeric_verdicts_20260918 --apply   # 实际写入

注意：本地与线上共用远程生产库，--apply 即直接修改生产数据。
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.models.project_artifact import ProjectArtifact  # noqa: E402
from app.models.task import TaskItemRecord  # noqa: E402
from app.models.template import TemplateItem  # noqa: E402

LEGACY_FAILURE_MESSAGE = (
    "该任务在错误信息留存能力上线前（2026-09-14）生成失败，未记录具体原因，"
    "请点击「重试」重新生成。"
)

# 无阈值数值项上的错误 pass：必须同时满足
#   1) task_item_records.result = 'pass' 且 result_value 非空（确为数值录入）
#   2) 对应模板项仍存在、check_type 为 numeric/score
#   3) numeric：min_value/max_value 均为空；score：pass_score 为空
NUMERIC_FALSE_PASS_SQL = text(
    """
    SELECT r.id AS record_id,
           r.task_id,
           r.template_item_id,
           r.result_value,
           t.check_type,
           t.min_value,
           t.max_value,
           t.pass_score
      FROM task_item_records r
      JOIN template_items t ON t.id = r.template_item_id
     WHERE r.result = 'pass'
       AND NULLIF(btrim(COALESCE(r.result_value, '')), '') IS NOT NULL
       AND (
             (LOWER(COALESCE(t.check_type, t.result_type, '')) = 'numeric'
                 AND t.min_value IS NULL AND t.max_value IS NULL)
          OR (LOWER(COALESCE(t.check_type, t.result_type, '')) = 'score'
                 AND t.pass_score IS NULL)
       )
    """
)


async def heal(apply: bool) -> None:
    mode = "【写入模式】" if apply else "【预演模式 · 不写入】"
    print(mode)

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(NUMERIC_FALSE_PASS_SQL)).mappings().all()
        print(f"[BUG-11] 命中无阈值却记为 pass 的数值/打分填报：{len(rows)} 条")
        for row in rows[:20]:
            print(
                f"  - record={row['record_id']} task={row['task_id']} "
                f"type={row['check_type']} value={row['result_value']}"
            )
        if len(rows) > 20:
            print(f"  … 其余 {len(rows) - 20} 条略")

        failed_jobs = (
            await db.execute(
                select(ProjectArtifact).where(
                    ProjectArtifact.artifact_type == "generation_job",
                    ProjectArtifact.status == "failed",
                    (ProjectArtifact.error_message.is_(None))
                    | (ProjectArtifact.error_message == ""),
                    ProjectArtifact.is_deleted.is_(False),
                )
            )
        ).scalars().all()
        print(f"[BUG-06] 命中缺少错误原因的失败生成任务：{len(failed_jobs)} 条")
        for job in failed_jobs[:10]:
            print(f"  - job={job.id} project={job.project_id} filename={job.filename}")

        if not apply:
            print("预演结束，未写入任何数据。确认无误后加 --apply 执行。")
            return

        if rows:
            ids = [row["record_id"] for row in rows]
            await db.execute(
                TaskItemRecord.__table__.update()
                .where(TaskItemRecord.__table__.c.id.in_(ids))
                .values(result=None)
            )
            print(f"[BUG-11] 已清空 {len(ids)} 条填报的 result（数值保留，归入「其他项」）")

        for job in failed_jobs:
            job.error_message = LEGACY_FAILURE_MESSAGE
        print(f"[BUG-06] 已回填 {len(failed_jobs)} 条失败任务的错误说明")

        await db.commit()
        print("已提交。")


def main() -> None:
    parser = argparse.ArgumentParser(description="数值项错误合格与空错误信息自愈")
    parser.add_argument("--apply", action="store_true", help="实际写入（默认只预演）")
    args = parser.parse_args()
    asyncio.run(heal(args.apply))


if __name__ == "__main__":
    main()
