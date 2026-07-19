"""P0-4 修复脚本：清理丢失的制品文件记录

问题：
- 生产环境部署时清理了 uploads/audit_projects/{pid}/artifacts/ 目录
- 但数据库 project_artifacts 表仍保留全部历史记录
- 导致 UI 显示 15 个可下载制品，实际全部 404

修复方案：
1. 扫描所有 project_artifacts 记录
2. 检查 path 字段指向的文件是否存在
3. 不存在的记录标记为 status='missing'，error_message 记录丢失时间
4. UI 接口过滤掉 status='missing' 的记录

使用方式：
    cd backend
    .venv/Scripts/python.exe -m scripts.cleanup_missing_artifacts
    或
    .venv/Scripts/python.exe scripts/cleanup_missing_artifacts.py --dry-run  # 仅查看
    .venv/Scripts/python.exe scripts/cleanup_missing_artifacts.py --execute  # 实际执行
"""

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# 保证可以 import app.*
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import AsyncSessionLocal  # noqa: E402
from app.models.project_artifact import ProjectArtifact  # noqa: E402

from sqlalchemy import select  # noqa: E402


async def cleanup(dry_run: bool = True) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ProjectArtifact).order_by(
                ProjectArtifact.project_id, ProjectArtifact.created_at
            )
        )
        items = result.scalars().all()
        total = len(items)
        missing = 0
        kept = 0
        for item in items:
            path = Path(item.path) if item.path else None
            file_exists = path.is_file() if path else False
            # generation_job 类型 path 为空字符串，跳过文件存在性检查
            is_metadata_only = item.artifact_type == "generation_job"
            if file_exists or is_metadata_only:
                kept += 1
                continue
            missing += 1
            project_no = "unknown"
            print(
                f"  MISSING id={item.id} project={item.project_id} "
                f"type={item.artifact_type} v{item.version} "
                f"path={item.path!r} status={item.status}"
            )
            if not dry_run:
                item.status = "missing"
                item.error_message = (
                    f"File lost during deployment cleanup at "
                    f"{datetime.now(timezone.utc).isoformat()}"
                )
        if not dry_run and missing:
            await db.commit()
        print()
        print(f"Total records: {total}")
        print(f"Kept (file exists): {kept}")
        print(f"Missing (file lost): {missing}")
        if dry_run:
            print()
            print("Dry run only. To actually update records, run with --execute")
        else:
            print()
            print(f"Updated {missing} records to status='missing'")
            print()
            print("UI 后续会自动过滤 status='missing' 的记录，不再显示为可下载")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="清理丢失的制品文件记录")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="仅扫描不修改数据库（默认行为，与 --execute 互斥）",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="实际执行更新（与 --dry-run 互斥）",
    )
    args = parser.parse_args()
    if args.dry_run and args.execute:
        print("Error: --dry-run and --execute are mutually exclusive")
        sys.exit(1)
    # 默认 dry-run
    if not args.execute:
        args.dry_run = True
    print("=" * 70)
    print("EFIS 制品文件丢失清理工具")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}")
    print()
    asyncio.run(cleanup(dry_run=args.dry_run))
