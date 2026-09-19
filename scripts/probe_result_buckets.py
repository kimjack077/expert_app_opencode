# -*- coding: utf-8 -*-
"""只读探查：判定值分布 + 观察项/待整改是否真实存在"""
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

for tbl, col in (('task_item_records', 'result'),
                 ('inspection_record_items', 'radio_value'),
                 ('inspection_record_items', 'result')):
    print("=== %s.%s 取值分布 ===" % (tbl, col))
    try:
        cur.execute('SELECT "%s", count(*) FROM "%s" GROUP BY 1 ORDER BY 2 DESC' % (col, tbl))
        rows = cur.fetchall()
        if not rows:
            print("   (空)")
        for r in rows:
            print("   %-28r %d" % (r[0], r[1]))
    except Exception as e:
        conn.rollback()
        print("   跳过：", e)
    print()

print("=== 检查项类型分布（template_items） ===")
cur.execute("""
    SELECT result_type, check_type, count(*)
    FROM template_items
    WHERE is_category IS NOT TRUE
    GROUP BY 1,2 ORDER BY 3 DESC
""")
for r in cur.fetchall():
    print("   result_type=%-12r check_type=%-10r %d" % r)

print()
print("=== 有数值/文本但无判定结论的项（即「其他项」） ===")
cur.execute("""
    SELECT count(*) FROM task_item_records
    WHERE result IS NULL AND (result_value IS NOT NULL AND result_value <> ''
                              OR result_text IS NOT NULL AND result_text <> '')
""")
print("   task_item_records:", cur.fetchone()[0])

cur.close()
conn.close()
