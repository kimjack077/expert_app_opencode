# -*- coding: utf-8 -*-
"""演示前只读体检 + 九幕主线自检。

全程 read-only（conn.set_session(readonly=True)），不写任何库。
用途：给老杨一份「演示前数据是否齐备」的准确清单与风险点。

用法::
    backend/.venv/Scripts/python.exe scripts/demo_readiness_check.py
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


def q(sql, args=()):
    cur.execute(sql, args)
    return cur.fetchall()


def head(title):
    print()
    print("=" * 74)
    print(title)
    print("=" * 74)


# ── 数据盘点 ────────────────────────────────────────────────────────────
head("一、演示数据盘点")

print("\n【企业】")
rows = q("""
    SELECT risk_level, count(*) FROM enterprises
    WHERE is_deleted IS NOT TRUE GROUP BY 1 ORDER BY 2 DESC
""")
for r in rows:
    print("   %-10s %d" % (r[0] or "(空)", r[1]))
print("   合计: %d" % sum(r[1] for r in rows))

print("\n【审核项目】")
rows = q("""
    SELECT status, count(*) FROM audit_projects
    WHERE is_deleted IS NOT TRUE GROUP BY 1 ORDER BY 2 DESC
""")
if not rows:
    print("   （无项目）")
for r in rows:
    print("   %-14s %d" % (r[0] or "(空)", r[1]))

print("\n【检查任务 inspection_tasks】")
rows = q("""
    SELECT status, count(*) FROM inspection_tasks
    WHERE is_deleted IS NOT TRUE GROUP BY 1 ORDER BY 2 DESC
""")
if not rows:
    print("   （无任务）")
for r in rows:
    print("   %-14s %d" % (r[0] or "(空)", r[1]))

print("\n【检查记录 inspection_records】")
rows = q("""
    SELECT status, count(*) FROM inspection_records
    WHERE is_deleted IS NOT TRUE GROUP BY 1 ORDER BY 2 DESC
""")
if not rows:
    print("   （无记录）")
for r in rows:
    print("   %-14s %d" % (r[0] or "(空)", r[1]))

print("\n【模板】")
rows = q("""
    SELECT is_published, count(*) FROM inspection_templates
    WHERE is_deleted IS NOT TRUE GROUP BY 1 ORDER BY 2 DESC
""")
for r in rows:
    print("   已发布=%-6s %d" % (r[0], r[1]))

print("\n【知识库】")
try:
    rows = q("SELECT status, count(*) FROM knowledge_documents WHERE is_deleted IS NOT TRUE GROUP BY 1")
    for r in rows:
        print("   %-14s %d" % (r[0] or "(空)", r[1]))
except Exception as e:
    conn.rollback()
    print("   （跳过：%s）" % e)

print("\n【用户】")
rows = q("""
    SELECT role, count(*) FROM users WHERE is_active IS NOT FALSE GROUP BY 1 ORDER BY 2 DESC
""")
for r in rows:
    print("   %-14s %d" % (r[0], r[1]))


# ── 九幕依赖自检 ────────────────────────────────────────────────────────
head("二、九幕主线自检")

# 第一幕 工作台
print("\n[第一幕] 智能工作台")
n_pending = q("SELECT count(*) FROM inspection_tasks WHERE is_deleted IS NOT TRUE AND status='pending'")[0][0]
n_doing = q("SELECT count(*) FROM inspection_tasks WHERE is_deleted IS NOT TRUE AND status='in_progress'")[0][0]
n_done = q("SELECT count(*) FROM inspection_tasks WHERE is_deleted IS NOT TRUE AND status='completed'")[0][0]
print("   任务：待处理 %d · 进行中 %d · 已完成 %d · 共 %d" % (n_pending, n_doing, n_done, n_pending + n_doing + n_done))
print("   %s" % ("✅ 有数据" if (n_pending + n_doing + n_done) > 0 else "⚠️ 无任务，工作台会空"))

# 第二幕 模板
print("\n[第二幕] 检查模板设计与防呆")
rows = q("""
    SELECT t.id, t.name,
           (SELECT count(*) FROM template_items ti
             WHERE ti.template_id = t.id AND ti.is_category IS NOT TRUE AND ti.is_deleted IS NOT TRUE) AS leaves
    FROM inspection_templates t WHERE t.is_deleted IS NOT TRUE ORDER BY leaves DESC LIMIT 5
""")
for r in rows:
    print("   %-34s 叶子项=%d" % ((r[1] or "")[:32], r[2]))
print("   %s" % ("✅ 有模板" if rows else "⚠️ 无模板"))

# 第三幕 知识库
print("\n[第三幕] 法规知识库")
try:
    n = q("SELECT count(*) FROM knowledge_documents WHERE is_deleted IS NOT TRUE")[0][0]
    print("   文档数：%d  %s" % (n, "✅" if n > 0 else "⚠️ 空"))
except Exception as e:
    conn.rollback()
    print("   （跳过：%s）" % e)

# 第四幕 企业档案
print("\n[第四幕] 企业档案与项目策划")
n_ent = q("SELECT count(*) FROM enterprises WHERE is_deleted IS NOT TRUE")[0][0]
n_prj = q("SELECT count(*) FROM audit_projects WHERE is_deleted IS NOT TRUE")[0][0]
print("   企业 %d · 审核项目 %d  %s" % (n_ent, n_prj, "✅" if (n_ent and n_prj) else "⚠️"))

# 第五幕 Agent + 会议
print("\n[第五幕] 智审 Agent 与会议管理")
try:
    n_meet = q("SELECT count(*) FROM communication_meetings")[0][0]
    print("   会议记录数：%d" % n_meet)
except Exception as e:
    conn.rollback()
    print("   （跳过：%s）" % e)
llm_ok = bool(env.get("LLM_API_KEY"))
print("   LLM 主通道已配置：%s" % ("是" if llm_ok else "否 ⚠️"))
print("   LLM 备份通道已配置：%s" % ("是" if env.get("LLM_BACKUP_API_KEY") else "否"))

# 第六/七幕 H5 现场检查
print("\n[第六/七幕] H5 现场检查与最终判定")
rows = q("""
    SELECT t.id, t.title, t.status,
      (SELECT count(*) FROM task_item_records tir WHERE tir.task_id = t.id) AS recs
    FROM inspection_tasks t
    WHERE t.is_deleted IS NOT TRUE AND t.status IN ('pending','in_progress')
    ORDER BY t.created_at DESC LIMIT 5
""")
if not rows:
    print("   ⚠️ 无「待处理/进行中」任务，H5 现场检查无入口")
for r in rows:
    print("   %-30s status=%-12s 已录=%d" % ((r[1] or "")[:28], r[2], r[3]))

# 第八幕 记录与报告
print("\n[第八幕] 记录追溯与报告生成")
n_sub = q("SELECT count(*) FROM inspection_records WHERE is_deleted IS NOT TRUE AND status='submitted'")[0][0]
print("   已提交记录：%d  %s" % (n_sub, "✅" if n_sub else "⚠️ 无已提交记录"))

# 第九幕 门禁与归档 —— 真跑门禁（这是唯一能确定第九幕走不走得通的方法）
print("\n[第九幕] 质量门禁与资料包交付（实测每个项目的 quality-check）")
rows = q("""
    SELECT id, title, status FROM audit_projects WHERE is_deleted IS NOT TRUE
    ORDER BY created_at DESC
""")

BASE = "http://127.0.0.1:8000"
token = None
try:
    import json
    import urllib.request

    req = urllib.request.Request(
        f"{BASE}/api/auth/login",
        data=json.dumps({"username": "admin", "password": "admin123"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        token = json.loads(resp.read().decode()).get("data", {}).get("access_token")
except Exception as exc:  # noqa: BLE001 — 体检脚本不应因登录失败中断
    print("   （跳过门禁实测：本地后端未启动或登录失败 —— %s）" % exc)

passed_count = 0
if token:
    for pid, title, st in rows:
        try:
            req = urllib.request.Request(
                f"{BASE}/api/audit-projects/{pid}/quality-check",
                data=b"",
                method="POST",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode())
            qc = payload.get("data", payload)
            if isinstance(qc, dict) and "quality_check" in qc:
                qc = qc["quality_check"]
            ok = bool(qc.get("passed"))
            passed_count += 1 if ok else 0
            blockers = ",".join(
                b.get("code", "") for b in (qc.get("blockers") or [])[:3]
            )
            print(
                "   %s %-38s score=%-4s 阻断=%d  %s"
                % ("✅" if ok else "❌", (title or str(pid))[:36],
                   qc.get("score"), qc.get("blocking_count", 0), blockers)
            )
        except Exception as exc:  # noqa: BLE001
            print("   ?  %-38s （查询失败：%s）" % ((title or str(pid))[:36], exc))
    print()
    print(
        "   **通过门禁的项目数：%d / %d**" % (passed_count, len(rows))
        + ("  ✅ 第九幕可走通" if passed_count else "  ⚠️ 第九幕「通过后下载归档包」会卡")
    )

# ── 风险提示 ────────────────────────────────────────────────────────────
head("三、风险提示")

print("""
1. 演示项目门禁当前**不通过**（score=75，阻断 UNSUBMITTED_RECORDS +
   INCOMPLETE_PLAN_ITEMS）→ 第九幕「通过后下载归档包」会卡。
   补齐需写生产库，须老杨确认。

2. 项目报告 PDF 需 `token` query 参数；门禁不通过时返回 409 并附详情。

3. 数值型检查项「重点耗能设备运行参数」本次被写入过测试值
   （现为 77.5），如需恢复请告知。
""")

cur.close()
conn.close()
