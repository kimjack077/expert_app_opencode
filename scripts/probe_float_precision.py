# -*- coding: utf-8 -*-
"""只读探查：定位 100.9000015258789 这类浮点残留的真实来源（可安全对生产库跑）"""
from pathlib import Path

env = {}
for line in Path('backend/.env').read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, v = line.split('=', 1)
    env[k.strip()] = v.strip()

import psycopg2

conn = psycopg2.connect(
    host=env['PG_HOST'], port=env['PG_PORT'], dbname=env['PG_DB'],
    user=env['PG_USER'], password=env['PG_PASSWORD'],
)
conn.set_session(readonly=True, autocommit=True)
cur = conn.cursor()

print("=== 1. 定位「重点耗能设备运行参数」检查项 ===")
cur.execute("""
    SELECT id, template_id, title, result_type, check_type, unit, min_value, max_value
    FROM template_items
    WHERE title LIKE '%耗能设备%' OR title LIKE '%运行参数%'
""")
items = cur.fetchall()
for r in items:
    print("  ", r)

print()
print("=== 2. 该检查项在各任务记录中的实际取值 ===")
cur.execute("""
    SELECT tir.id, tir.task_id, tir.result, tir.result_value, tir.result_text, tir.recorded_at
    FROM task_item_records tir
    JOIN template_items ti ON ti.id = tir.template_item_id
    WHERE ti.title LIKE '%耗能设备%' OR ti.title LIKE '%运行参数%'
    ORDER BY tir.recorded_at DESC NULLS LAST
""")
for r in cur.fetchall():
    print("  ", r)

print()
print("=== 3. 所有可能承载数值的列，其类型 ===")
cur.execute("""
    SELECT table_name, column_name, data_type, numeric_precision, numeric_scale
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND (column_name LIKE '%value%' OR column_name LIKE '%numeric%'
           OR column_name LIKE '%score%' OR column_name LIKE '%result%'
           OR column_name LIKE '%reading%' OR column_name LIKE '%measured%')
    ORDER BY data_type, table_name, column_name
""")
for r in cur.fetchall():
    print("  ", r)

print()
print("=== 4. 全库扫描：哪些文本列存在「小数位>=5」的残留 ===")
cur.execute("""
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND data_type IN ('character varying','text','character')
""")
text_cols = cur.fetchall()
hits = []
for t, c, d in text_cols:
    try:
        cur.execute(
            'SELECT count(*) FROM "%s" WHERE "%s" ~ \'^-?[0-9]+\\.[0-9]{5,}$\'' % (t, c)
        )
        n = cur.fetchone()[0]
        if n:
            hits.append((t, c, n))
    except Exception:
        conn.rollback()
print("   命中：", hits if hits else "无")

print()
print("=== 5. 全库扫描：REAL(float4) 列（精度丢失根源） ===")
cur.execute("""
    SELECT table_name, column_name
    FROM information_schema.columns
    WHERE table_schema = 'public' AND data_type = 'real'
    ORDER BY table_name
""")
for r in cur.fetchall():
    print("  ", r)

cur.close()
conn.close()
