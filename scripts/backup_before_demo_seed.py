"""生产库受影响表快照备份（只读源库 + 新建备份表，不修改任何业务数据）。

用法：
    cd backend && .venv\\Scripts\\python.exe ..\\scripts\\backup_before_demo_seed.py
    cd backend && .venv\\Scripts\\python.exe ..\\scripts\\backup_before_demo_seed.py --apply

默认 dry-run，只打印将要创建的备份表；加 --apply 才真正建表。
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import psycopg2  # noqa: E402
from app.config import settings  # noqa: E402

# 本次演示数据补齐会触及的表
TABLES = [
    "inspection_templates",
    "template_items",
    "inspection_tasks",
    "task_item_records",
    "inspection_records",
    "inspection_record_items",
    "audit_projects",
    "audit_plan_items",
    "communication_meetings",
    "enterprises",
    "knowledge_documents",
    "users",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="真正创建备份表")
    parser.add_argument("--suffix", default=None, help="备份表后缀，默认按日期")
    args = parser.parse_args()

    suffix = args.suffix or datetime.now().strftime("%Y%m%d")
    conn = psycopg2.connect(
        host=settings.PG_HOST,
        port=settings.PG_PORT,
        dbname=settings.PG_DB,
        user=settings.PG_USER,
        password=settings.PG_PASSWORD,
    )
    conn.autocommit = True
    cur = conn.cursor()

    print(f"目标库：{settings.PG_HOST}:{settings.PG_PORT}/{settings.PG_DB}")
    print(f"备份后缀：_bak_{suffix}")
    print(f"模式：{'APPLY' if args.apply else 'DRY-RUN'}")
    print("-" * 72)

    created = 0
    for table in TABLES:
        cur.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name=%s",
            (table,),
        )
        if cur.fetchone()[0] == 0:
            print(f"  跳过（表不存在）: {table}")
            continue

        cur.execute(f'SELECT count(*) FROM "{table}"')
        rows = cur.fetchone()[0]
        bak = f"{table}_bak_{suffix}"

        if args.apply:
            cur.execute(f'CREATE TABLE IF NOT EXISTS "{bak}" AS TABLE "{table}"')
            cur.execute(f'SELECT count(*) FROM "{bak}"')
            bak_rows = cur.fetchone()[0]
            created += 1
            print(f"  ✅ {table:28s} {rows:>6} 行  →  {bak} ({bak_rows} 行)")
        else:
            print(f"  · {table:28s} {rows:>6} 行  →  {bak}")

    print("-" * 72)
    print(f"{'已创建' if args.apply else '将创建'} {created if args.apply else len(TABLES)} 张备份表")

    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name LIKE '%%_bak_%%' "
        "ORDER BY table_name"
    )
    existing = [r[0] for r in cur.fetchall()]
    print(f"库内现有备份表 {len(existing)} 张：")
    for name in existing:
        print(f"  - {name}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
