#!/usr/bin/env python3
"""测试库 vs 生产库 —— **只读**结构对比。

═══════════════════════════════════════════════════════════════════════════
 为什么需要它
═══════════════════════════════════════════════════════════════════════════
本仓库的本地开发库与线上生产**共用同一个远程 PostgreSQL 实例**
（49.232.213.79），只是库名不同：

    db_expert_claude   生产（线上跑的就是它）
    db_expert_test     测试（自动化测试专用，可随意写脏）

于是每次测试完都必须回答一个问题：**测试库里改了什么，需不需要迁到生产？**

* 结构（DDL）改了 → 必须同步，否则线上代码与表结构不匹配
* 只是数据被写脏 → **不需要也不应该**迁到生产

这个脚本用实测给出答案，不靠"我觉得没改"。

═══════════════════════════════════════════════════════════════════════════
 安全性
═══════════════════════════════════════════════════════════════════════════
**全程只读**：只跑 ``information_schema`` / ``pg_catalog`` 查询，
不执行任何 DDL/DML。生产库连接仅用于读取元数据。

═══════════════════════════════════════════════════════════════════════════
 用法
═══════════════════════════════════════════════════════════════════════════
    cd backend
    .venv\\Scripts\\python.exe ..\\scripts\\compare_db_schema.py
    .venv\\Scripts\\python.exe ..\\scripts\\compare_db_schema.py --test-db db_expert_test --prod-db db_expert_claude
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 只读查询：列定义
COLUMNS_SQL = """
select table_name, column_name, data_type, is_nullable,
       coalesce(column_default, ''), coalesce(character_maximum_length, -1),
       coalesce(numeric_precision, -1)
from information_schema.columns
where table_schema = 'public'
order by table_name, column_name
"""

# 只读查询：索引
INDEXES_SQL = """
select tablename, indexname, indexdef
from pg_indexes
where schemaname = 'public'
order by tablename, indexname
"""

# 只读查询：约束（主键/唯一/外键）
CONSTRAINTS_SQL = """
select tc.table_name, tc.constraint_name, tc.constraint_type
from information_schema.table_constraints tc
where tc.table_schema = 'public'
order by tc.table_name, tc.constraint_name
"""

# 只读查询：Alembic 版本
ALEMBIC_SQL = "select version_num from alembic_version"


async def _fetch(db_name: str, sql: str) -> list[tuple]:
    import asyncpg

    from app.config import settings

    conn = await asyncpg.connect(
        host=settings.PG_HOST,
        port=int(settings.PG_PORT),
        user=settings.PG_USER,
        password=settings.PG_PASSWORD,
        database=db_name,
        timeout=30,
    )
    try:
        rows = await conn.fetch(sql)
        return [tuple(r) for r in rows]
    finally:
        await conn.close()


async def _fetch_safe(db_name: str, sql: str) -> list[tuple]:
    try:
        return await _fetch(db_name, sql)
    except Exception as exc:  # noqa: BLE001
        print(f"  [警告] 读取 {db_name} 失败：{type(exc).__name__}: {exc}")
        return []


def _diff(label: str, prod: list[tuple], test: list[tuple]) -> bool:
    """打印差异；返回是否存在差异。"""
    prod_set, test_set = set(prod), set(test)
    only_prod = sorted(prod_set - test_set)
    only_test = sorted(test_set - prod_set)

    if not only_prod and not only_test:
        print(f"  [一致] {label}（{len(prod_set)} 项）")
        return False

    print(f"  [差异] {label}")
    if only_test:
        print(f"    ── 仅测试库有（{len(only_test)} 项）—— 生产缺失，需迁移 ──")
        for row in only_test[:60]:
            print(f"      + {row}")
        if len(only_test) > 60:
            print(f"      …… 另有 {len(only_test) - 60} 项")
    if only_prod:
        print(f"    ── 仅生产库有（{len(only_prod)} 项）—— 测试库落后 ──")
        for row in only_prod[:60]:
            print(f"      - {row}")
        if len(only_prod) > 60:
            print(f"      …… 另有 {len(only_prod) - 60} 项")
    return True


async def main() -> int:
    parser = argparse.ArgumentParser(description="测试库 vs 生产库结构对比（只读）")
    parser.add_argument("--test-db", default="db_expert_test")
    parser.add_argument("--prod-db", default="db_expert_claude")
    args = parser.parse_args()

    from app.config import settings

    print("=" * 72)
    print("EFIS 数据库结构对比（只读，不写任何库）")
    print("=" * 72)
    print(f"  实例：{settings.PG_HOST}:{settings.PG_PORT}")
    print(f"  生产：{args.prod_db}")
    print(f"  测试：{args.test_db}")
    print()

    print("[1/4] 对比列定义（表结构）……")
    prod_cols = await _fetch_safe(args.prod_db, COLUMNS_SQL)
    test_cols = await _fetch_safe(args.test_db, COLUMNS_SQL)
    cols_diff = _diff("列定义", prod_cols, test_cols)
    print()

    print("[2/4] 对比索引……")
    prod_idx = await _fetch_safe(args.prod_db, INDEXES_SQL)
    test_idx = await _fetch_safe(args.test_db, INDEXES_SQL)
    idx_diff = _diff("索引", prod_idx, test_idx)
    print()

    print("[3/4] 对比约束（主键/唯一/外键）……")
    prod_con = await _fetch_safe(args.prod_db, CONSTRAINTS_SQL)
    test_con = await _fetch_safe(args.test_db, CONSTRAINTS_SQL)
    con_diff = _diff("约束", prod_con, test_con)
    print()

    print("[4/4] 对比 Alembic 迁移版本……")
    prod_ver = await _fetch_safe(args.prod_db, ALEMBIC_SQL)
    test_ver = await _fetch_safe(args.test_db, ALEMBIC_SQL)
    ver_diff = _diff("Alembic 版本", prod_ver, test_ver)
    print()

    print("=" * 72)
    if cols_diff or idx_diff or con_diff or ver_diff:
        print("结论：**存在结构差异**，需要迁移（或确认差异是否有意为之）。")
        print()
        print("处置建议：")
        print("  1. 若「仅测试库有」→ 测试库领先，说明有迁移未在生产执行：")
        print("     cd backend && alembic upgrade head")
        print("  2. 若「仅生产库有」→ 测试库落后，重建测试库：")
        print("     CREATE DATABASE db_expert_test TEMPLATE db_expert_claude;")
        print("  3. 差异若属手工试验遗留，请在测试库中回滚，不要在生产执行。")
        return 1

    print("结论：结构完全一致，**无需迁移**。")
    print("      测试期间只写了数据，没有 DDL 变更。")
    print("      测试库中的测试数据不应迁入生产。")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
