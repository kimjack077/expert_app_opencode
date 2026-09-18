"""EFIS 数据体检（只读）。

把"数据不一致"类缺陷变成可批量扫描的检查项。第三方测试反复发现的问题中，
有相当一部分不是接口报错，而是**库里本来就存在脏数据或关联断裂**：

  · 记录只填了企业名称、没关联企业主数据  → 页面显示"-"
  · 子记录挂在已软删除的父记录上        → 点进去 404
  · 判定型检查项被写入了数值/文本        → 报告显示异常
  · 已软删除的项目下仍挂着未删除的任务    → 任务列表点不开

这些靠人工点页面很难发现，但一条 SQL 就能扫出来。

═══════════════════════════════════════════════════════════════════════════
 安全说明
═══════════════════════════════════════════════════════════════════════════
本脚本**全程只读**（``set_session(readonly=True)``），可以安全地对生产库运行。

用法::

    cd backend && .venv\\Scripts\\python.exe ..\\scripts\\db_health_check.py
    .venv\\Scripts\\python.exe ..\\scripts\\db_health_check.py --db db_expert_test
    .venv\\Scripts\\python.exe ..\\scripts\\db_health_check.py --out 体检报告.md
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from dataclasses import dataclass, field

import psycopg2

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1] / "backend"


# ---------------------------------------------------------------------------
# 检查项定义
# ---------------------------------------------------------------------------
# severity: 严重（影响用户可见结果）/ 警告（数据质量）/ 提示（设计观察）


@dataclass
class Check:
    key: str
    severity: str
    title: str
    impact: str
    sql: str
    sample_sql: str | None = None
    hint: str = ""


CHECKS: list[Check] = [
    # ── A. 软删除一致性 ────────────────────────────────────────────────
    Check(
        key="A1",
        severity="严重",
        title="未删除的检查明细挂在已软删的记录上",
        impact="详情接口按记录存活过滤 → 明细成了孤儿；统计若不过滤则数字虚高",
        sql="""SELECT count(*) FROM inspection_record_items i
               JOIN inspection_records r ON r.id = i.record_id
               WHERE r.is_deleted = true""",
    ),
    Check(
        key="A2",
        severity="严重",
        title="未删除的检查项挂在已软删的模板上",
        impact="模板列表看不到，但检查项仍在库内被统计",
        sql="""SELECT count(*) FROM template_items ti
               JOIN inspection_templates t ON t.id = ti.template_id
               WHERE t.is_deleted = true AND ti.is_deleted = false""",
    ),
    Check(
        key="A3",
        severity="严重",
        title="未删除的审核计划项挂在已软删的项目上",
        impact="「我的审核任务」会列出这些任务，点进去必定 404（外部测试 P0-29 根因）",
        sql="""SELECT count(*) FROM audit_plan_items p
               JOIN audit_projects pr ON pr.id = p.project_id
               WHERE pr.is_deleted = true AND p.is_deleted = false""",
        sample_sql="""SELECT p.id, p.area_name, pr.title
                      FROM audit_plan_items p
                      JOIN audit_projects pr ON pr.id = p.project_id
                      WHERE pr.is_deleted = true AND p.is_deleted = false
                      LIMIT 5""",
        hint="治本做法：项目软删时级联软删其计划项",
    ),
    Check(
        key="A4",
        severity="警告",
        title="未删除的任务挂在已软删的项目上",
        impact="任务列表可见但所属项目已归档，操作时报错",
        sql="""SELECT count(*) FROM inspection_tasks t
               JOIN audit_plan_items p ON p.inspection_task_id = t.id
               JOIN audit_projects pr ON pr.id = p.project_id
               WHERE pr.is_deleted = true AND t.is_deleted = false""",
    ),
    Check(
        key="A5",
        severity="警告",
        title="未删除的记录关联了已软删的企业",
        impact="打开记录时请求企业风险画像会返回 404，前端曾直接把英文报错弹给用户",
        sql="""SELECT count(*) FROM inspection_records r
               JOIN enterprises e ON e.id = r.enterprise_id
               WHERE e.is_deleted = true AND r.is_deleted = false""",
        sample_sql="""SELECT r.id, r.enterprise_name, r.status
                      FROM inspection_records r
                      JOIN enterprises e ON e.id = r.enterprise_id
                      WHERE e.is_deleted = true AND r.is_deleted = false
                      LIMIT 5""",
    ),
    Check(
        key="A6",
        severity="警告",
        title="未删除的记录关联了已软删的模板",
        impact="记录详情/报告生成时可能取不到模板项",
        sql="""SELECT count(*) FROM inspection_records r
               JOIN inspection_templates t ON t.id = r.template_id
               WHERE t.is_deleted = true AND r.is_deleted = false""",
    ),
    Check(
        key="A7",
        severity="提示",
        title="软删除标记与删除时间不一致（is_deleted=true 但 deleted_at 为空）",
        impact="审计追溯时无法确定删除时间",
        sql="""SELECT
                 (SELECT count(*) FROM inspection_records WHERE is_deleted = true AND deleted_at IS NULL)
               + (SELECT count(*) FROM inspection_templates WHERE is_deleted = true AND deleted_at IS NULL)
               + (SELECT count(*) FROM enterprises WHERE is_deleted = true AND deleted_at IS NULL)
               + (SELECT count(*) FROM audit_projects WHERE is_deleted = true AND deleted_at IS NULL)
               + (SELECT count(*) FROM inspection_tasks WHERE is_deleted = true AND deleted_at IS NULL)""",
    ),

    # ── B. 主数据关联完整性 ───────────────────────────────────────────
    Check(
        key="B1",
        severity="警告",
        title="记录只填了企业名称、未关联企业主数据（有名无 ID）",
        impact="地址/联系人/信用代码等字段取不到值，H5 上显示为「-」（外部测试 P1-33 根因）",
        sql="""SELECT count(*) FROM inspection_records
               WHERE is_deleted = false
                 AND enterprise_id IS NULL
                 AND enterprise_name IS NOT NULL AND enterprise_name <> ''""",
        sample_sql="""SELECT id, enterprise_name, status FROM inspection_records
                      WHERE is_deleted = false AND enterprise_id IS NULL
                        AND enterprise_name IS NOT NULL AND enterprise_name <> ''
                      LIMIT 5""",
        hint="建议创建记录时按名称反查并回填 enterprise_id",
    ),
    Check(
        key="B2",
        severity="严重",
        title="记录的企业 ID 指向不存在的企业（外键孤儿）",
        impact="数据引用断裂，详情页取企业信息必然失败",
        sql="""SELECT count(*) FROM inspection_records r
               LEFT JOIN enterprises e ON e.id = r.enterprise_id
               WHERE r.enterprise_id IS NOT NULL AND e.id IS NULL""",
    ),
    Check(
        key="B3",
        severity="警告",
        title="记录引用了不存在的模板（外键孤儿）",
        impact="报告无法装配检查项，生成报告会失败或空白",
        sql="""SELECT count(*) FROM inspection_records r
               LEFT JOIN inspection_templates t ON t.id = r.template_id
               WHERE t.id IS NULL""",
    ),
    Check(
        key="B4",
        severity="警告",
        title="计划项引用了不存在的检查任务（外键孤儿）",
        impact="任务列表与项目计划对不上",
        sql="""SELECT count(*) FROM audit_plan_items p
               LEFT JOIN inspection_tasks t ON t.id = p.inspection_task_id
               WHERE p.inspection_task_id IS NOT NULL AND t.id IS NULL""",
    ),

    # ── C. 模板树结构完整性 ───────────────────────────────────────────
    Check(
        key="C1",
        severity="严重",
        title="检查项的父节点不存在（树结构断裂）",
        impact="模板树渲染时该节点及其子树整体丢失（外部测试 P0-01「条目丢失」同类根因）",
        sql="""SELECT count(*) FROM template_items c
               LEFT JOIN template_items p ON p.id = c.parent_id
               WHERE c.parent_id IS NOT NULL AND p.id IS NULL""",
        sample_sql="""SELECT c.id, c.title, c.template_id FROM template_items c
                      LEFT JOIN template_items p ON p.id = c.parent_id
                      WHERE c.parent_id IS NOT NULL AND p.id IS NULL
                      LIMIT 5""",
    ),
    Check(
        key="C2",
        severity="严重",
        title="检查项的父节点属于另一个模板（跨模板挂靠）",
        impact="一个模板的树里混入别的模板的节点，条目数量统计错乱",
        sql="""SELECT count(*) FROM template_items c
               JOIN template_items p ON p.id = c.parent_id
               WHERE c.template_id <> p.template_id""",
    ),
    Check(
        key="C3",
        severity="警告",
        title="模板树存在循环引用（自己指向自己）",
        impact="递归构建树时会无限循环或栈溢出",
        sql="SELECT count(*) FROM template_items WHERE parent_id = id",
    ),

    # ── D. 检查项数据质量 ─────────────────────────────────────────────
    Check(
        key="D1",
        severity="严重",
        title="检查结论使用了非法的枚举值",
        impact="前端映射表查不到 → 页面显示英文原文或空白（外部测试 P0-05 字典混乱）",
        sql="""SELECT count(*) FROM inspection_record_items
               WHERE radio_value IS NOT NULL AND radio_value <> ''
                 AND lower(trim(radio_value)) NOT IN (
                   'pass','fail','na','not_applicable','not-applicable','n/a',
                   'compliant','qualified','non_compliant','unqualified',
                   'pending_rectification','observe'
                 )""",
        sample_sql="""SELECT radio_value, count(*) FROM inspection_record_items
                      WHERE radio_value IS NOT NULL AND radio_value <> ''
                        AND lower(trim(radio_value)) NOT IN (
                          'pass','fail','na','not_applicable','not-applicable','n/a',
                          'compliant','qualified','non_compliant','unqualified',
                          'pending_rectification','observe')
                      GROUP BY radio_value ORDER BY 2 DESC LIMIT 10""",
    ),
    Check(
        key="D2",
        severity="严重",
        title="判定型检查项（radio）被写入了数值或文本",
        impact="判定列取不到值 → 报告显示「-」，且被判为「未填写」（外部测试 C6 脏数据）",
        sql="""SELECT count(*) FROM inspection_record_items
               WHERE item_check_type = 'radio'
                 AND (numeric_value IS NOT NULL
                      OR (text_value IS NOT NULL AND text_value <> ''))""",
        sample_sql="""SELECT id, item_title, radio_value, numeric_value, text_value
                      FROM inspection_record_items
                      WHERE item_check_type = 'radio'
                        AND (numeric_value IS NOT NULL
                             OR (text_value IS NOT NULL AND text_value <> ''))
                      LIMIT 5""",
        hint="建议在写入侧按 check_type 做字段白名单校验",
    ),
    Check(
        key="D3",
        severity="警告",
        title="分类节点被写入了检查结论",
        impact="分类节点本不参与判定，却被计入统计（外部测试 P0-02「根节点显示未填写」）",
        sql="""SELECT count(*) FROM inspection_record_items i
               JOIN template_items ti ON ti.id = i.template_item_id
               WHERE ti.is_category = true
                 AND i.radio_value IS NOT NULL AND i.radio_value <> ''""",
    ),

    # ── E. 状态一致性 ─────────────────────────────────────────────────
    Check(
        key="E1",
        severity="严重",
        title="已提交的记录没有任何检查明细",
        impact="报告空白、统计全 0，用户会认为数据丢失",
        sql="""SELECT count(*) FROM inspection_records r
               WHERE r.is_deleted = false AND r.status = 'submitted'
                 AND NOT EXISTS (SELECT 1 FROM inspection_record_items i WHERE i.record_id = r.id)""",
    ),
    Check(
        key="E2",
        severity="严重",
        title="已提交的记录中所有检查项都未填写",
        impact="报告显示全部「-」，合规率 0%，属明显异常数据",
        sql="""SELECT count(*) FROM inspection_records r
               WHERE r.is_deleted = false AND r.status = 'submitted'
                 AND EXISTS (SELECT 1 FROM inspection_record_items i WHERE i.record_id = r.id)
                 AND NOT EXISTS (
                   SELECT 1 FROM inspection_record_items i
                   WHERE i.record_id = r.id
                     AND i.radio_value IS NOT NULL AND i.radio_value <> ''
                 )""",
        sample_sql="""SELECT r.id, r.enterprise_name, r.status, r.inspection_date
                      FROM inspection_records r
                      WHERE r.is_deleted = false AND r.status = 'submitted'
                        AND EXISTS (SELECT 1 FROM inspection_record_items i WHERE i.record_id = r.id)
                        AND NOT EXISTS (
                          SELECT 1 FROM inspection_record_items i
                          WHERE i.record_id = r.id
                            AND i.radio_value IS NOT NULL AND i.radio_value <> ''
                        )
                      LIMIT 5""",
    ),
    Check(
        key="E3",
        severity="警告",
        title="已提交记录中存在必填判定项未填写",
        impact="报告不完整，但不影响提交——校验规则可能被绕过",
        sql="""SELECT count(*) FROM inspection_record_items i
               JOIN inspection_records r ON r.id = i.record_id
               WHERE r.is_deleted = false AND r.status = 'submitted'
                 AND i.item_check_type = 'radio'
                 AND (i.radio_value IS NULL OR i.radio_value = '')""",
    ),
    Check(
        key="E4",
        severity="警告",
        title="已完成的任务没有产生任何检查记录",
        impact="任务显示已完成，但查不到检查内容",
        sql="""SELECT count(*) FROM inspection_tasks t
               WHERE t.is_deleted = false AND t.status = 'completed'
                 AND NOT EXISTS (
                   SELECT 1 FROM audit_plan_items p
                   WHERE p.inspection_task_id = t.id AND p.template_id IS NOT NULL
                 )""",
        hint="近似检查：仅统计未挂任何模板的计划项的任务",
    ),

    # ── F. 唯一性与编号 ───────────────────────────────────────────────
    Check(
        key="F1",
        severity="严重",
        title="未删除的模板存在重复编码（code）",
        impact="新建模板时会报「编码已存在」，但列表里又只看到一条",
        sql="""SELECT count(*) FROM (
                 SELECT code FROM inspection_templates
                 WHERE is_deleted = false AND code IS NOT NULL AND code <> ''
                 GROUP BY code HAVING count(*) > 1
               ) x""",
    ),
    Check(
        key="F2",
        severity="严重",
        title="未删除的任务存在重复编号（task_no）",
        impact="任务编号是业务凭证号，重复会导致对账困难",
        sql="""SELECT count(*) FROM (
                 SELECT task_no FROM inspection_tasks
                 WHERE is_deleted = false AND task_no IS NOT NULL
                 GROUP BY task_no HAVING count(*) > 1
               ) x""",
    ),
    Check(
        key="F3",
        severity="警告",
        title="未删除的企业存在重复统一社会信用代码",
        impact="同一家企业被重复建档，审核记录分散在多条企业下",
        sql="""SELECT count(*) FROM (
                 SELECT credit_code FROM enterprises
                 WHERE is_deleted = false AND credit_code IS NOT NULL AND credit_code <> ''
                 GROUP BY credit_code HAVING count(*) > 1
               ) x""",
    ),
]


# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------


def load_env() -> dict:
    env_path = BACKEND_DIR / ".env"
    if not env_path.exists():
        sys.exit(f"找不到配置文件：{env_path}")
    env = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def run_checks(db_name: str, env: dict, verbose: bool) -> tuple[list[dict], int]:
    conn = psycopg2.connect(
        host=env["PG_HOST"], port=env.get("PG_PORT", "5432"),
        user=env["PG_USER"], password=env["PG_PASSWORD"], dbname=db_name,
    )
    # 只读：本脚本绝不写库
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor()

    results = []
    for chk in CHECKS:
        try:
            cur.execute(chk.sql)
            row = cur.fetchone()
            count = int(row[0]) if row and row[0] is not None else 0
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            results.append({"check": chk, "count": None, "error": str(e)[:160], "samples": []})
            continue

        samples = []
        if count > 0 and chk.sample_sql:
            try:
                cur.execute(chk.sample_sql)
                samples = cur.fetchall()
            except Exception:  # noqa: BLE001
                conn.rollback()

        results.append({"check": chk, "count": count, "error": None, "samples": samples})

    cur.close()
    conn.close()
    return results, 0


def render_markdown(db_name: str, results: list[dict], verbose: bool) -> str:
    lines = [f"# EFIS 数据体检报告", "", f"**体检对象**：`{db_name}`", ""]

    problems = [r for r in results if (r["count"] or 0) > 0 or r["error"]]
    errors = [r for r in results if r["error"]]
    clean = [r for r in results if not r["error"] and (r["count"] or 0) == 0]

    by_sev: dict[str, list[dict]] = {}
    for r in problems:
        by_sev.setdefault(r["check"].severity, []).append(r)

    lines += [
        "## 结论速览", "",
        f"- 检查项总数：**{len(results)}**",
        f"- 发现问题：**{len(problems)}**",
        f"- 通过：**{len(clean)}**",
        f"- 执行失败：**{len(errors)}**",
        "",
    ]

    if not problems:
        lines += ["**所有检查项均通过，未发现数据一致性问题。**", ""]
        return "\n".join(lines)

    lines += ["| 严重度 | 数量 |", "|---|---:|"]
    for sev in ("严重", "警告", "提示"):
        if sev in by_sev:
            lines.append(f"| {sev} | {len(by_sev[sev])} |")
    lines.append("")

    for sev in ("严重", "警告", "提示"):
        if sev not in by_sev:
            continue
        lines += [f"## {sev}（{len(by_sev[sev])} 项）", ""]
        for r in by_sev[sev]:
            chk = r["check"]
            if r["error"]:
                lines += [f"### {chk.key} {chk.title}", "", f"- ⚠️ 检查执行失败：`{r['error']}`", ""]
                continue
            lines += [
                f"### {chk.key} {chk.title}",
                "",
                f"- **命中行数**：{r['count']}",
                f"- **影响**：{chk.impact}",
            ]
            if chk.hint:
                lines.append(f"- **建议**：{chk.hint}")
            if r["samples"] and verbose:
                lines += ["", "```"]
                for s in r["samples"]:
                    lines.append(" | ".join(str(x) for x in s))
                lines += ["```"]
            lines.append("")

    if clean:
        lines += ["## 通过的检查项", ""]
        for r in clean:
            lines.append(f"- ✅ {r['check'].key} {r['check'].title}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="EFIS 数据体检（只读）")
    parser.add_argument("--db", default=None, help="目标库名，默认取 .env 中的 PG_DB")
    parser.add_argument("--out", default=None, help="把 Markdown 报告写入文件")
    parser.add_argument("--quiet", action="store_true", help="不打印样例明细")
    args = parser.parse_args()

    env = load_env()
    db_name = args.db or env.get("PG_DB")
    if not db_name:
        sys.exit("未能确定目标库名")

    print(f"体检目标：{env['PG_HOST']}/{db_name}（只读）\n")
    results, _ = run_checks(db_name, env, verbose=not args.quiet)

    report = render_markdown(db_name, results, verbose=not args.quiet)
    print(report)

    if args.out:
        pathlib.Path(args.out).write_text(report, encoding="utf-8")
        print(f"\n报告已写入：{args.out}")

    problems = [r for r in results if (r["count"] or 0) > 0]
    severe = [r for r in problems if r["check"].severity == "严重"]
    print(f"\n汇总：{len(problems)} 项发现问题（其中严重 {len(severe)} 项），"
          f"{len([r for r in results if not r['error'] and (r['count'] or 0) == 0])} 项通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
