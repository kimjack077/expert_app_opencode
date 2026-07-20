"""Synchronize completed legacy inspection tasks into formal audit records.

The command is read-only by default. Use ``--execute`` to persist changes.
Each task is committed independently so one bad legacy task cannot roll back
other successful conversions.
"""

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select

# Allow ``python scripts/sync_formal_audit_records.py`` from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import AsyncSessionLocal, engine  # noqa: E402
from app.models.audit_project import (  # noqa: E402
    AuditAreaRecord,
    AuditPlanItem,
    AuditProject,
    Nonconformity,
)
from app.models.record import InspectionRecordItem  # noqa: E402
from app.models.task import InspectionTask, TaskItemRecord  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.formal_audit_sync_service import (  # noqa: E402
    sync_task_to_formal_record,
)


def has_meaningful_result(row: TaskItemRecord) -> bool:
    return bool(
        str(row.result or "").strip()
        or str(row.result_value or "").strip()
        or str(row.result_text or "").strip()
        or str(row.inspector_note or "").strip()
    )


async def list_candidate_refs(task_ids: list[UUID]) -> list[tuple[UUID, UUID]]:
    async with AsyncSessionLocal() as db:
        stmt = (
            select(AuditPlanItem.id, InspectionTask.id)
            .join(
                InspectionTask,
                AuditPlanItem.inspection_task_id == InspectionTask.id,
            )
            .join(AuditProject, AuditPlanItem.project_id == AuditProject.id)
            .where(
                AuditPlanItem.is_deleted.is_(False),
                AuditProject.is_deleted.is_(False),
                InspectionTask.is_deleted.is_(False),
                InspectionTask.status == "completed",
            )
            .order_by(AuditPlanItem.created_at, AuditPlanItem.id)
        )
        if task_ids:
            stmt = stmt.where(InspectionTask.id.in_(task_ids))
        return [(row[0], row[1]) for row in (await db.execute(stmt)).all()]


async def load_task_context(db, plan_item_id: UUID, task_id: UUID, lock: bool = False):
    plan_stmt = select(AuditPlanItem).where(
        AuditPlanItem.id == plan_item_id,
        AuditPlanItem.is_deleted.is_(False),
    )
    if lock:
        plan_stmt = plan_stmt.with_for_update()
    plan_item = (await db.execute(plan_stmt)).scalar_one_or_none()
    task = (
        await db.execute(
            select(InspectionTask).where(
                InspectionTask.id == task_id,
                InspectionTask.is_deleted.is_(False),
                InspectionTask.status == "completed",
            )
        )
    ).scalar_one_or_none()
    if not plan_item or not task or plan_item.inspection_task_id != task.id:
        return None
    active_project_id = (
        await db.execute(
            select(AuditProject.id).where(
                AuditProject.id == plan_item.project_id,
                AuditProject.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if not active_project_id:
        return None

    rows = (
        await db.execute(
            select(TaskItemRecord)
            .where(TaskItemRecord.task_id == task.id)
            .order_by(TaskItemRecord.recorded_at, TaskItemRecord.id)
        )
    ).scalars().all()
    meaningful_rows = [row for row in rows if has_meaningful_result(row)]
    template_item_ids = [
        str(row.template_item_id) for row in meaningful_rows if row.template_item_id
    ]
    duplicate_template_item_ids = sorted(
        item_id
        for item_id, count in Counter(template_item_ids).items()
        if count > 1
    )
    missing_template_item_count = sum(
        1 for row in meaningful_rows if not row.template_item_id
    )

    recorder_candidates = [
        task.assigned_to,
        *(row.recorded_by for row in meaningful_rows),
        *(plan_item.assigned_member_ids or []),
    ]
    recorded_by = None
    seen = set()
    for candidate in recorder_candidates:
        if not candidate or str(candidate) in seen:
            continue
        seen.add(str(candidate))
        user_id = (
            await db.execute(
                select(User.id).where(
                    User.id == candidate,
                )
            )
        ).scalar_one_or_none()
        if user_id:
            recorded_by = user_id
            break

    formal_records = (
        await db.execute(
            select(AuditAreaRecord)
            .where(
                AuditAreaRecord.project_id == plan_item.project_id,
                AuditAreaRecord.plan_item_id == plan_item.id,
            )
            .order_by(AuditAreaRecord.created_at)
        )
    ).scalars().all()
    record_ids = [record.id for record in formal_records]
    formal_item_count = 0
    if record_ids:
        formal_item_count = int(
            (
                await db.execute(
                    select(func.count(InspectionRecordItem.id)).where(
                        InspectionRecordItem.audit_area_record_id.in_(record_ids)
                    )
                )
            ).scalar_one()
        )

    return {
        "plan_item": plan_item,
        "task": task,
        "meaningful_rows": meaningful_rows,
        "recorded_by": recorded_by,
        "formal_records": formal_records,
        "formal_item_count": formal_item_count,
        "missing_template_item_count": missing_template_item_count,
        "duplicate_template_item_ids": duplicate_template_item_ids,
        "can_populate_empty_formal": bool(
            len(formal_records) == 1
            and formal_item_count == 0
            and formal_records[0].status != "reviewed"
        ),
    }


def describe_context(context) -> str:
    task = context["task"]
    plan_item = context["plan_item"]
    formal_records = context["formal_records"]
    formal_numbers = ",".join(record.record_no or str(record.id) for record in formal_records)
    formal_statuses = ",".join(record.status or "-" for record in formal_records)
    legacy_results = Counter(
        str(row.result or "value_only") for row in context["meaningful_rows"]
    )
    legacy_result_summary = ",".join(
        f"{value}:{count}" for value, count in sorted(legacy_results.items())
    )
    reason = "ready"
    if not context["meaningful_rows"]:
        reason = "skip:no_meaningful_rows"
    elif context["missing_template_item_count"]:
        reason = "skip:missing_template_item"
    elif context["duplicate_template_item_ids"]:
        reason = "skip:duplicate_template_item"
    elif not context["recorded_by"]:
        reason = "skip:no_valid_recorder"
    elif formal_records and not context["can_populate_empty_formal"]:
        reason = "skip:formal_record_exists"
    elif context["can_populate_empty_formal"]:
        reason = "ready:populate_empty_formal_record"
    return (
        f"task={task.id} task_no={task.task_no} project={plan_item.project_id} "
        f"plan_item={plan_item.id} area={plan_item.area_name!r} "
        f"legacy_rows={len(context['meaningful_rows'])} "
        f"legacy_results={legacy_result_summary or '-'} "
        f"missing_template_items={context['missing_template_item_count']} "
        f"duplicate_template_items={','.join(context['duplicate_template_item_ids']) or '-'} "
        f"formal_records={len(formal_records)} formal_items={context['formal_item_count']} "
        f"recorded_by={context['recorded_by'] or '-'} "
        f"record_nos={formal_numbers or '-'} record_statuses={formal_statuses or '-'} "
        f"action={reason}"
    )


async def scan(refs: list[tuple[UUID, UUID]]) -> dict[str, int]:
    totals = {
        "ready": 0,
        "existing": 0,
        "no_rows": 0,
        "no_recorder": 0,
        "invalid_rows": 0,
    }
    async with AsyncSessionLocal() as db:
        for plan_item_id, task_id in refs:
            context = await load_task_context(db, plan_item_id, task_id)
            if not context:
                continue
            print(describe_context(context))
            if not context["meaningful_rows"]:
                totals["no_rows"] += 1
            elif context["missing_template_item_count"] or context["duplicate_template_item_ids"]:
                totals["invalid_rows"] += 1
            elif not context["recorded_by"]:
                totals["no_recorder"] += 1
            elif context["formal_records"] and not context["can_populate_empty_formal"]:
                totals["existing"] += 1
            else:
                totals["ready"] += 1
    return totals


async def execute_sync(refs: list[tuple[UUID, UUID]]) -> dict[str, int]:
    totals = {
        "created": 0,
        "populated_empty": 0,
        "existing": 0,
        "no_rows": 0,
        "no_recorder": 0,
        "invalid_rows": 0,
        "failed": 0,
    }
    for plan_item_id, task_id in refs:
        async with AsyncSessionLocal() as db:
            try:
                context = await load_task_context(db, plan_item_id, task_id, lock=True)
                if not context:
                    print(f"SKIP task={task_id} reason=candidate_changed")
                    continue
                print(describe_context(context))
                if not context["meaningful_rows"]:
                    totals["no_rows"] += 1
                    continue
                if context["missing_template_item_count"] or context["duplicate_template_item_ids"]:
                    totals["invalid_rows"] += 1
                    continue
                if not context["recorded_by"]:
                    totals["no_recorder"] += 1
                    continue
                # Existing formal evidence may have been edited by an auditor.
                # Only an unreviewed record with zero items is safe to populate.
                if context["formal_records"] and not context["can_populate_empty_formal"]:
                    totals["existing"] += 1
                    continue

                populated_empty = context["can_populate_empty_formal"]
                area_record = await sync_task_to_formal_record(
                    db,
                    context["task"],
                    context["plan_item"],
                    context["recorded_by"],
                )
                await db.commit()
                if populated_empty:
                    totals["populated_empty"] += 1
                else:
                    totals["created"] += 1
                print(f"SYNCED task={task_id} formal_record={area_record.id}")
            except Exception as exc:  # keep task transactions isolated
                await db.rollback()
                totals["failed"] += 1
                print(f"FAILED task={task_id} error={type(exc).__name__}: {exc}")
    return totals


async def verify(refs: list[tuple[UUID, UUID]]) -> dict[str, int]:
    task_ids = [task_id for _, task_id in refs]
    plan_item_ids = [plan_item_id for plan_item_id, _ in refs]
    if not refs:
        return {"tasks": 0, "formal_records": 0, "formal_items": 0, "nonconformities": 0}

    async with AsyncSessionLocal() as db:
        record_ids = (
            await db.execute(
                select(AuditAreaRecord.id).where(
                    AuditAreaRecord.plan_item_id.in_(plan_item_ids)
                )
            )
        ).scalars().all()
        formal_items = 0
        if record_ids:
            formal_items = int(
                (
                    await db.execute(
                        select(func.count(InspectionRecordItem.id)).where(
                            InspectionRecordItem.audit_area_record_id.in_(record_ids)
                        )
                    )
                ).scalar_one()
            )
        nc_count = int(
            (
                await db.execute(
                    select(func.count(Nonconformity.id)).where(
                        Nonconformity.plan_item_id.in_(plan_item_ids)
                    )
                )
            ).scalar_one()
        )
        return {
            "tasks": len(task_ids),
            "formal_records": len(record_ids),
            "formal_items": formal_items,
            "nonconformities": nc_count,
        }


async def main(execute: bool, task_ids: list[UUID]) -> int:
    engine.echo = False
    all_refs = await list_candidate_refs(task_ids)
    print(f"mode={'EXECUTE' if execute else 'DRY_RUN'} candidates={len(all_refs)}")
    if not all_refs:
        print("No completed linked legacy tasks found.")
        await engine.dispose()
        return 0

    task_ref_counts = Counter(task_id for _, task_id in all_refs)
    ambiguous_task_ids = {
        task_id for task_id, count in task_ref_counts.items() if count > 1
    }
    for task_id in sorted(ambiguous_task_ids, key=str):
        plan_ids = [str(plan_id) for plan_id, ref_task_id in all_refs if ref_task_id == task_id]
        print(
            f"SKIP task={task_id} reason=multiple_plan_items "
            f"plan_items={','.join(plan_ids)}"
        )
    refs = [ref for ref in all_refs if ref[1] not in ambiguous_task_ids]

    if execute:
        totals = await execute_sync(refs)
        totals["multiple_plan_tasks"] = len(ambiguous_task_ids)
        print(f"execution_summary={totals}")
    else:
        totals = await scan(refs)
        totals["multiple_plan_tasks"] = len(ambiguous_task_ids)
        print(f"dry_run_summary={totals}")

    verification = await verify(all_refs)
    print(f"verification={verification}")
    await engine.dispose()
    return 1 if execute and totals.get("failed", 0) else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sync completed legacy tasks into formal audit area records"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Persist synchronization (default is a read-only dry run)",
    )
    parser.add_argument(
        "--task-id",
        action="append",
        default=[],
        type=UUID,
        help="Limit to one task UUID; may be supplied more than once",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.execute, args.task_id)))
