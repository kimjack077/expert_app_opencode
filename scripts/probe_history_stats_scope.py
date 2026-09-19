# -*- coding: utf-8 -*-
"""只读核查：历史检查记录统计（records.py:1804-1806 只看 radio_value）会不会漏计。

背景：该接口对 InspectionRecordItem 逐个取 classify_result(i.radio_value)，
而权威口径 classify_item 是「radio_value → result → evaluation_3level」优先级。
若存在 radio_value 为空、判定值落在 result 的条目，这里就会漏计。
"""
from __future__ import annotations

from pathlib import Path

env = {}
for line in Path("backend/.env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip()

import psycopg2

conn = psycopg2.connect(
    host=env["PG_HOST"], port=env["PG_PORT"], dbname=env["PG_DB"],
    user=env["PG_USER"], password=env["PG_PASSWORD"],
)
conn.set_session(readonly=True, autocommit=True)
cur = conn.cursor()

print("=" * 76)
print("InspectionRecordItem：radio_value 为空、但 result 有判定值 的条目")
print("=" * 76)

cur.execute("""
    SELECT count(*) FROM inspection_record_items
    WHERE (radio_value IS NULL OR btrim(radio_value) = '')
      AND result IS NOT NULL AND btrim(result) <> ''
""")
n_all = cur.fetchone()[0]
print("全部条目：%d" % n_all)

cur.execute("""
    SELECT count(*) FROM inspection_record_items iri
    JOIN inspection_records ir ON ir.id = iri.record_id
    WHERE (iri.radio_value IS NULL OR btrim(iri.radio_value) = '')
      AND iri.result IS NOT NULL AND btrim(iri.result) <> ''
      AND ir.status = 'submitted'
""")
n_submitted = cur.fetchone()[0]
print("其中「已提交」记录下的：%d   ← 该接口只统计 submitted 的记录" % n_submitted)

print()
print("=== 这些条目的 result 取值分布 ===")
cur.execute("""
    SELECT iri.result, count(*) FROM inspection_record_items iri
    JOIN inspection_records ir ON ir.id = iri.record_id
    WHERE (iri.radio_value IS NULL OR btrim(iri.radio_value) = '')
      AND iri.result IS NOT NULL AND btrim(iri.result) <> ''
      AND ir.status = 'submitted'
    GROUP BY 1 ORDER BY 2 DESC
""")
rows = cur.fetchall()
for r in rows:
    print("   result=%-12r %d" % r)
if not rows:
    print("   （无）")

print()
print("=" * 76)
print("对比：两种口径在同一批「已提交」条目上的计数差")
print("=" * 76)
cur.execute("""
    SELECT
      -- 旧口径：只看 radio_value
      sum(CASE WHEN iri.radio_value IN ('pass','compliant','qualified','1') THEN 1 ELSE 0 END),
      -- 权威口径：radio_value → result
      sum(CASE WHEN COALESCE(NULLIF(btrim(iri.radio_value),''), NULLIF(btrim(iri.result),''))
                    IN ('pass','compliant','qualified','1') THEN 1 ELSE 0 END)
    FROM inspection_record_items iri
    JOIN inspection_records ir ON ir.id = iri.record_id
    WHERE ir.status = 'submitted'
""")
old, new = cur.fetchone()
print("   合格：旧口径(只看 radio_value) = %s" % old)
print("        权威口径(radio→result)   = %s" % new)
print("        差额 = %s" % ((new or 0) - (old or 0)))

cur.close()
conn.close()
