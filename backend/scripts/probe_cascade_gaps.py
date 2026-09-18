"""只读探查：通用地找出所有「活子行挂在软删父行上」的外键组合。

不写死 A1/A2/A3 —— 从 ``information_schema`` 动态发现外键关系，
再逐个检查是否违反了「父已删、子未删」的一致性。

全程 ``readonly=True``。

    python scripts/probe_cascade_gaps.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2  # noqa: E402

from app.config import settings  # noqa: E402

# 发现所有外键：子表.列 → 父表.列
FK_SQL = """
SELECT
    tc.table_name        AS child_table,
    kcu.column_name      AS child_column,
    ccu.table_name       AS parent_table,
    ccu.column_name      AS parent_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
     ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
     ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public'
ORDER BY tc.table_name, kcu.column_name
"""

SOFT_DELETE_TABLES_SQL = """
SELECT table_name FROM information_schema.columns
WHERE table_schema = 'public' AND column_name = 'is_deleted'
"""


def main() -> int:
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor()

    cur.execute(SOFT_DELETE_TABLES_SQL)
    soft_tables = {row[0] for row in cur.fetchall()}
    print(f"支持软删除的表（{len(soft_tables)} 张）：")
    print("  " + ", ".join(sorted(soft_tables)))
    print()

    cur.execute(FK_SQL)
    fks = cur.fetchall()

    findings = []
    for child_table, child_column, parent_table, parent_column in fks:
        # 只关心「父表支持软删」的关系；父表不支持软删就谈不上"父已删"
        if parent_table not in soft_tables or parent_column != "id":
            continue

        child_has_soft = child_table in soft_tables
        child_filter = (
            f"AND c.is_deleted = false" if child_has_soft else ""
        )

        sql = f"""
            SELECT count(*) FROM {child_table} c
            JOIN {parent_table} p ON p.id = c.{child_column}
            WHERE p.is_deleted = true {child_filter}
        """
        try:
            cur.execute(sql)
            count = cur.fetchone()[0]
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            print(f"  SKIP {child_table}.{child_column} → {parent_table}: {str(exc)[:70]}")
            continue

        if count:
            findings.append(
                (child_table, child_column, parent_table, child_has_soft, count)
            )

    print("=" * 78)
    print("「父已软删、子未删」的命中情况")
    print("=" * 78)
    if not findings:
        print("  无（全部一致）")
    for child_table, child_column, parent_table, child_has_soft, count in sorted(
        findings, key=lambda r: -r[4]
    ):
        kind = "子表支持软删 → 应级联软删" if child_has_soft else "子表是硬删除表 → 应随父硬删"
        print(f"  {count:>6}  {child_table}.{child_column} → {parent_table}    {kind}")

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
