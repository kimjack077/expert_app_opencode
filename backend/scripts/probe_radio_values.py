"""只读探查：各判定字段的真实取值分布。

用途：收敛统计口径前，先确认数据库里实际存在哪些判定值，
避免"按代码猜取值"——历史缺陷正是这么产生的。

    python scripts/probe_radio_values.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2  # noqa: E402

from app.config import settings  # noqa: E402

TARGETS = [
    ("inspection_record_items", "radio_value"),
    ("inspection_record_items", "result"),
    ("task_item_records", "result"),
    ("inspection_records", "overall_result"),
    ("audit_area_records", "evaluation_3level"),
    ("audit_area_records", "result"),
]


def main() -> int:
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor()
    for table, column in TARGETS:
        print(f"\n== {table}.{column} ==")
        try:
            cur.execute(
                f"SELECT {column}, count(*) FROM {table} "  # noqa: S608 - 表名列名来自白名单常量
                f"GROUP BY 1 ORDER BY 2 DESC LIMIT 20"
            )
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            print(f"   SKIP: {type(exc).__name__}: {str(exc)[:100]}")
            continue
        rows = cur.fetchall()
        if not rows:
            print("   (空表)")
        for value, count in rows:
            print(f"   {value!r:30} {count}")
    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
