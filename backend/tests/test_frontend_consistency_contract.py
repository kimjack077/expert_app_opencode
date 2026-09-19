"""契约层测试：前端展示口径一致性（防复发门禁）。

═══════════════════════════════════════════════════════════════════════════
 为什么要有这个文件
═══════════════════════════════════════════════════════════════════════════
2026-09-19 复核外部测试提交的 8 条前端问题，确认 7 条成立、1 条不成立。
本文件把这些修复**固化为静态断言**——同类问题在下一轮外部测试中不得再流出。

覆盖的缺陷（编号沿用外部测试清单）：

* ISSUE-01 步骤条把「已填写但非判定型」的项渲染成 ``·``，看起来像漏填
* ISSUE-02 检查结果汇总卡缺「其他项」，导致各分类之和 ≠ 总检查项
* ISSUE-03 审核排期把数据库原始 ISO-8601 串直接渲染给客户
* ISSUE-04 数值框浮点精度残留（复核**不成立**，此处只钉死「不得引入 float32 收窄」）
* ISSUE-05 模板「编辑检查项」默认落在旧版编辑器
* ISSUE-06 登录页硬编码「6 重全要素质量门禁」（与门禁真实输出条数不符）
* ISSUE-07 检查项汇总「符合项/不符合项」与「合格项/不合格项」两套术语并存
* ISSUE-08 H5 底部固定提交栏未预留安全区

全部为**静态文件扫描**，不需要数据库，可作提交前秒级门禁::

    .venv\\Scripts\\python.exe -m pytest tests/test_frontend_consistency_contract.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
WEB = REPO_ROOT / "web-admin" / "src"
H5 = REPO_ROOT / "h5-app" / "src"

INSPECTION_FORM = WEB / "components" / "InspectionForm" / "index.tsx"
COMPLETION_UTIL = WEB / "utils" / "completion.ts"
DISPLAY_UTIL = WEB / "utils" / "display.ts"
PLAN_EDITOR = WEB / "pages" / "AuditProjects" / "components" / "PlanEditor.tsx"
PROJECT_DETAIL = WEB / "pages" / "AuditProjects" / "Detail.tsx"
TEMPLATES_PAGE = WEB / "pages" / "Templates" / "index.tsx"
LOGIN_PAGE = WEB / "pages" / "Login" / "index.tsx"
RECORDS_PAGE = WEB / "pages" / "Records" / "index.tsx"
H5_EXECUTION = H5 / "views" / "InspectionExecution.vue"


def _read(path: Path) -> str:
    assert path.exists(), f"文件不存在，路径可能已变更：{path}"
    return path.read_text(encoding="utf-8")


def _client_files(exts: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for root in (WEB, H5):
        if not root.exists():
            continue
        for ext in exts:
            files.extend(root.rglob(f"*{ext}"))
    return sorted(f for f in files if "node_modules" not in f.parts)


# ───────────────────────────────────────────────────────────────────────────
# ISSUE-01 / ISSUE-02 · 检查项分档必须走唯一来源
# ───────────────────────────────────────────────────────────────────────────


def test_completion_util_exposes_bucket_classifier():
    """`classifyItem` / `countBuckets` 是 Web 端分档的唯一来源。"""
    src = _read(COMPLETION_UTIL)
    assert "export function classifyItem" in src, "completion.ts 必须导出 classifyItem"
    assert "export function countBuckets" in src, "completion.ts 必须导出 countBuckets"
    assert "export type ItemBucket" in src

    # 五档齐备，缺一档就破坏了加法闭合
    for bucket in ("pass", "fail", "na", "other", "unfilled"):
        assert f"'{bucket}'" in src, f"ItemBucket 缺档位：{bucket}"


def test_inspection_form_uses_shared_classifier_not_handrolled_counts():
    """汇总计数不得再手写 ``radio_value === 'pass'`` —— 那是口径分叉的起点。"""
    src = _read(INSPECTION_FORM)

    assert "from '@/utils/completion'" in src, "InspectionForm 必须从 completion.ts 引入"
    assert "countBuckets(" in src, "汇总计数必须走 countBuckets"
    assert "classifyItem(" in src, "完成态判定必须走 classifyItem"

    handrolled = re.findall(
        r"flatItems\.filter\(\s*\(item\)\s*=>\s*item\.radio_value\s*===", src
    )
    assert not handrolled, (
        "InspectionForm 又出现了手写的 radio_value 计数（口径分叉）：\n  "
        + "\n  ".join(handrolled)
    )


def test_summary_card_renders_other_bucket():
    """汇总卡必须有「其他项」—— 否则 合格+不合格+不适用 < 总检查项。"""
    src = _read(INSPECTION_FORM)
    assert 'title="其他项"' in src, "检查结果汇总卡缺「其他项」格子"
    assert "otherCount" in src

    # 提交确认弹窗是同一语义的第二个消费点，必须同步
    assert "其他（数值/描述等）" in src, "提交确认弹窗的汇总未同步「其他项」"
    assert "共计：" in src, "提交确认弹窗未给出总计，用户无法自行对账"


def test_step_bar_no_longer_renders_dot_for_completed_items():
    """已完成项不得渲染成 ``·``；完成态标记表必须覆盖 other 档。"""
    src = _read(INSPECTION_FORM)

    assert "const STEP_MARK" in src, "步骤条完成态标记应集中为 STEP_MARK 表"
    assert re.search(r"other:\s*\{", src), "STEP_MARK 缺 other 档，数值/描述型项仍会无标记"

    # 旧的兜底渲染：isDone ? (isPass ? ' ✓' : isFail ? ' ✕' : ' ·')
    assert "? ' ✕' : ' ·'" not in src, "步骤条仍保留把已完成项渲染成「·」的旧兜底"
    assert "' ·'" not in src, "步骤条仍存在「·」兜底字面量"


def test_step_bar_colors_live_in_css_not_inline():
    """完成态配色必须写在 index.css 里。

    全局 ``.ant-btn-default`` 的 border / color / background 都带 ``!important``，
    组件内联样式覆盖不了 —— 写成内联等于没写（这正是本缺陷"无完成态高亮"的根因）。
    """
    src = _read(INSPECTION_FORM)
    assert "preset.cls" in src, "步骤条应通过 className 应用完成态配色"

    # STEP_MARK 表里不得再夹带内联配色（内联会被 .ant-btn-default 的 !important 吃掉）
    mark_block = re.search(r"const STEP_MARK[^=]*=\s*\{(.*?)\n\}", src, re.S)
    assert mark_block, "未找到 STEP_MARK 定义"
    assert "borderColor" not in mark_block.group(1), (
        "STEP_MARK 仍在用内联 borderColor —— 会被 .ant-btn-default 的 !important 吃掉，"
        "配色必须写在 index.css 的 .ant-btn.efis-step-* 里"
    )

    css = _read(WEB / "index.css")
    for cls in ("efis-step-pass", "efis-step-fail", "efis-step-na", "efis-step-other"):
        # 选择器组可能写作 `.ant-btn.X,\n.ant-btn.X:hover,\n.ant-btn.X:focus {`
        rule = re.search(r"\.ant-btn\.%s\b[^{]*\{" % cls, css)
        assert rule, f"index.css 缺完成态样式类 .ant-btn.{cls}"
    # 特异性必须高于 .ant-btn-default（两级类选择器），否则同样被 !important 压掉
    assert ".ant-btn.efis-step-pass" in css
    assert css.count("efis-step-") >= 8, "完成态样式类覆盖不全（含 :hover/:focus 变体）"


# ───────────────────────────────────────────────────────────────────────────
# ISSUE-03 · 日期一律走格式化，禁止裸渲染 ISO 串
# ───────────────────────────────────────────────────────────────────────────

# JSX 里直接插值 ``{project.scheduled_start}`` / 模板串 ``${project.scheduled_end}``
_RAW_JSX_DATE = re.compile(r"\{[^{}\n]*\.scheduled_(?:start|end)\s*\}")
_RAW_TEMPLATE_DATE = re.compile(r"\$\{[^}\n]*\.scheduled_(?:start|end)[^}\n]*\}")


def test_display_util_exposes_date_formatter():
    src = _read(DISPLAY_UTIL)
    assert "export function formatBusinessDate" in src
    assert "export function formatDateRange" in src
    # slice(0,10) 取的是 UTC 日期，与业务时区（UTC+8）差一天，不能作为主实现
    assert "dayjs(value)" in src, "formatBusinessDate 应按业务时区解析，而非字符串截断"


def test_no_raw_iso_datetime_rendered_in_client_tsx():
    """前端 TSX 不得把后端原始 ISO-8601 串直接渲染给客户。"""
    offenders: list[str] = []
    for path in _client_files((".tsx", ".vue")):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith(("//", "*", "/*")):
                continue
            if _RAW_JSX_DATE.search(line) or _RAW_TEMPLATE_DATE.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
    assert not offenders, (
        "以下位置仍在裸渲染 ISO-8601 时间串，应改用 formatDateRange / formatBusinessDate：\n  "
        + "\n  ".join(offenders)
    )


def test_plan_editor_and_detail_agree_on_date_formatting():
    """同一「审核排期」在计划页与详情页必须同一口径。"""
    for path in (PLAN_EDITOR, PROJECT_DETAIL):
        src = _read(path)
        assert "formatDateRange" in src, f"{path.name} 未使用统一的排期格式化"


# ───────────────────────────────────────────────────────────────────────────
# ISSUE-04 · 不得引入 float32 收窄（精度残留的唯一可能来源）
# ───────────────────────────────────────────────────────────────────────────


def test_no_float32_narrowing_in_clients():
    """复核结论：ISSUE-04 在现有数据与代码下不复现。

    实测 ``task_item_records.result_value`` 是 ``varchar(50)``，库里存的是干净的
    ``100.9``；全库无 float4 列、无小数位 ≥5 的残留。唯一能凭空造出
    ``100.9000015258789`` 的路径是 JS 侧 float32 收窄，故把它钉死。
    """
    offenders: list[str] = []
    for path in _client_files((".ts", ".tsx", ".vue", ".js")):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if re.search(r"\b(Float32Array|Math\.fround)\b", line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
    assert not offenders, "前端出现了 float32 收窄，会让数值回显出现长小数：\n  " + "\n  ".join(
        offenders
    )


# ───────────────────────────────────────────────────────────────────────────
# ISSUE-05 · 模板编辑器默认进 V2
# ───────────────────────────────────────────────────────────────────────────


def test_template_editor_defaults_to_v2():
    src = _read(TEMPLATES_PAGE)
    match = re.search(r"useState<'v1' \| 'v2'>\((\'[^']*\')\)", src)
    assert match, "未找到 editorVersion 的 useState 声明，模板页结构可能已变更"
    assert match.group(1) == "'v2'", (
        "「编辑检查项」默认进入旧版编辑器，演示人员看不到树形防呆；应默认 'v2'"
    )


# ───────────────────────────────────────────────────────────────────────────
# ISSUE-06 · 门禁文案不得写死条数
# ───────────────────────────────────────────────────────────────────────────


def test_gate_wording_does_not_hardcode_check_count():
    """门禁实际按 13 类阻断 + 5 类提醒动态输出，写死「6 重」与事实不符。

    正则用 ``(?<![\\d-])`` 排除 ``P2-08 重点`` 这类误报
    （编号里的「8」后紧跟「重」字，不是门禁条数）。
    """
    pattern = re.compile(r"(?<![\d-])[0-9]+\s*重")
    offenders: list[str] = []
    for path in _client_files((".ts", ".tsx", ".vue")):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
    assert not offenders, "登录页/文案仍在写死门禁条数：\n  " + "\n  ".join(offenders)

    login = _read(LOGIN_PAGE)
    assert "多重要素质量门禁" in login, "登录页门禁文案应改为「多重要素质量门禁」"


def test_gate_wording_scanner_selfcheck():
    """扫描器自检：认出真实现，且不被编号里的「重」字带偏。"""
    pattern = re.compile(r"(?<![\d-])[0-9]+\s*重")
    assert pattern.search("执行 6 重全要素质量门禁把关") is not None
    assert pattern.search("title: '🔒 6重质量门禁与交付归档包'") is not None
    assert pattern.search("title: '字段严谨重命名（P2-08 重点）'") is None
    assert pattern.search("门禁全部通过后") is None


# ───────────────────────────────────────────────────────────────────────────
# ISSUE-07 · 检查项汇总术语统一
# ───────────────────────────────────────────────────────────────────────────


def test_check_item_summary_uses_unified_terminology():
    """「符合项」在系统里是另一实体（项目下正式开具的不符合项单据），
    检查项汇总必须用「合格项 / 不合格项」，与现场执行页、H5 一致。"""
    src = _read(RECORDS_PAGE)
    # 只查统计卡里的裸「符合项」；「不符合项」作为业务实体可出现在别处
    assert ">合格项<" in src or "合格项" in src
    assert ">不符合项<" not in src, "检查记录抽屉仍在用「不符合项」标签"

    # 检查执行页与 H5 的口径作为基准，不得被反向改回
    assert "合格项" in _read(INSPECTION_FORM)
    assert "合格项" in _read(H5_EXECUTION)


# ───────────────────────────────────────────────────────────────────────────
# ISSUE-08 · H5 底部固定栏预留安全区
# ───────────────────────────────────────────────────────────────────────────


def test_h5_action_bar_reserves_safe_area():
    src = _read(H5_EXECUTION)

    bar = re.search(r"\.action-bar\s*\{[^}]*\}", src)
    assert bar, "未找到 .action-bar 样式规则"
    assert "env(safe-area-inset-bottom" in bar.group(0), (
        ".action-bar 未预留 env(safe-area-inset-bottom)，"
        "全面屏机型上主按钮会与手势条重叠"
    )

    # 固定栏变高后，内容区留白必须同步，否则最后一项被遮住
    page = re.search(r"\.inspection-execution-page\s*\{[^}]*\}", src)
    assert page, "未找到 .inspection-execution-page 样式规则"
    assert "env(safe-area-inset-bottom" in page.group(0), (
        "内容区 padding-bottom 未跟随 .action-bar 高度增加安全区，"
        "全面屏机型上页面底部内容会被底栏遮挡"
    )
