"""只读探查：模板检查项 result_options 的真实结构形态。

写入侧校验需要知道「允许的取值集合」，而该字段是自由 JSON。
本脚本把库中出现的结构形态归类，避免按猜测写校验逻辑。

    python scripts/probe_result_options.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2  # noqa: E402

from app.config import settings  # noqa: E402


def shape_of(value) -> str:
    if value is None:
        return "None"
    if isinstance(value, dict):
        return "dict(" + ",".join(sorted(value.keys()))[:80] + ")"
    if isinstance(value, list):
        if not value:
            return "list(empty)"
        inner = value[0]
        if isinstance(inner, dict):
            return "list[dict(" + ",".join(sorted(inner.keys()))[:60] + ")]"
        return f"list[{type(inner).__name__}]"
    return type(value).__name__


def main() -> int:
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor()

    cur.execute(
        "SELECT check_type, result_options FROM template_items "
        "WHERE result_options IS NOT NULL LIMIT 400"
    )
    rows = cur.fetchall()

    by_check: dict[str, Counter] = {}
    samples: dict[str, str] = {}
    for check_type, raw in rows:
        if raw is None:
            value = None
        elif isinstance(raw, (dict, list)):
            value = raw
        else:
            try:
                value = json.loads(raw)
            except (TypeError, ValueError):
                value = str(raw)
        shape = shape_of(value)
        by_check.setdefault(check_type or "(null)", Counter())[shape] += 1
        samples.setdefault(shape, json.dumps(value, ensure_ascii=False)[:260])

    print(f"共 {len(rows)} 条含 result_options 的模板项\n")
    for check_type, counter in sorted(by_check.items()):
        print(f"== check_type = {check_type!r} ==")
        for shape, count in counter.most_common():
            print(f"   {count:>4}  {shape}")
    print("\n== 结构样例 ==")
    for shape, sample in samples.items():
        print(f"\n--- {shape} ---\n{sample}")

    cur.execute("SELECT check_type, count(*) FROM template_items GROUP BY 1 ORDER BY 2 DESC")
    print("\n== template_items.check_type 分布 ==")
    for check_type, count in cur.fetchall():
        print(f"   {check_type!r:22} {count}")

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
