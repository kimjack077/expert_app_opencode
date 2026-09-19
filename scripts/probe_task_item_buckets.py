# -*- coding: utf-8 -*-
"""只读核对：演示任务的 4 个检查项类型与结果（用于验证分档口径）"""
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

TASK = 'cc0c73de-b299-4989-821e-179ba184459f'
print("=== 任务 %s 的检查项 ===" % TASK[:8])
cur.execute("""
    SELECT tir.id, ti.title, ti.result_type, ti.check_type, ti.min_value, ti.max_value,
           tir.result, tir.result_value, tir.result_text
    FROM task_item_records tir
    LEFT JOIN template_items ti ON ti.id = tir.template_item_id
    WHERE tir.task_id = %s
    ORDER BY ti.sort_order, ti.title
""", (TASK,))
rows = cur.fetchall()
print("   共 %d 项" % len(rows))
for r in rows:
    print("   title=%-22s result_type=%-10s check_type=%-6s min=%-6s max=%-6s | result=%-6s value=%-8s text=%s"
          % (r[1], r[2], r[3], r[4], r[5], r[6], r[7], (r[8] or '')[:20]))

print()
print("=== 按「判定型才计入三级判定」重算分档 ===")
buckets = {'pass': 0, 'fail': 0, 'na': 0, 'other': 0, 'unfilled': 0}
for r in rows:
    title, rtype, ctype, result, value, text = r[1], r[2], r[3], r[6], r[7], r[8]
    # resolveCheckType 规则：check_type 非默认(radio)则用它，否则用 result_type 非默认(pass_fail)的
    ct = (ctype or '').strip().lower()
    rt = (rtype or '').strip().lower()
    kind = ct if (ct and ct != 'radio') else (rt if (rt and rt != 'pass_fail') else 'radio')
    filled = bool((result or '').strip() or (value or '').strip() or (text or '').strip())
    if not filled:
        b = 'unfilled'
    elif kind != 'radio':
        b = 'other'
    elif result in ('pass', 'compliant'):
        b = 'pass'
    elif result in ('fail', 'non_compliant'):
        b = 'fail'
    elif result in ('na', 'not_applicable'):
        b = 'na'
    else:
        b = 'other'
    buckets[b] += 1
    print("   %-22s kind=%-8s -> %s" % (title, kind, b))
print("   汇总:", buckets)
print("   闭合校验: pass+fail+na+other+unfilled = %d, 总项 = %d -> %s"
      % (sum(buckets.values()), len(rows),
         'OK' if sum(buckets.values()) == len(rows) else 'MISMATCH'))

cur.close()
conn.close()
