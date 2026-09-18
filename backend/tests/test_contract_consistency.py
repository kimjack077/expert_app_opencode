"""契约层测试：统计口径唯一性。

═══════════════════════════════════════════════════════════════════════════
 为什么要有这个文件
═══════════════════════════════════════════════════════════════════════════
两轮第三方测试共报出 34 项问题，其中「数据不一致」类（数量对不上、
合格率对不上、报告与详情对不上）占比最高。追根溯源只有一个机制：

    **同一个业务语义（如"不适用"）在代码里被各自实现了很多份。**

于是修好一处、漏掉五处，线上就继续不一致。2026-09 那轮"统一口径"
只把 ``records.py`` 收敛到了 ``app/utils/item_stats.py``，而
``report_service.py`` / ``analytics.py`` / ``tasks.py`` / ``llm_service.py``
等 6 处仍然各写各的 —— 缺陷因此复发。

本文件用静态扫描把这件事变成**可自动拦截的回归门禁**：

* 2026-09-17 已完成全量收敛：原 6 处历史实现（``analytics.py`` ×2、
  ``tasks.py``、``llm_service.py``、``report_service.py``、
  ``formal_audit_sync_service.py``）全部改为调用 ``item_stats``；
* 债务清单 ``KNOWN_DEBT`` / ``HANDROLL_DEBT`` 已归零，本测试自此为**纯门禁**：
  任何新增的口径实现点都会立即失败并打印位置；
* 若确需新增，正解是复用 ``app.utils.item_stats``，而非重新登记债务。

本文件不需要数据库，随时可跑::

    .venv\\Scripts\\python.exe -m pytest tests/test_contract_consistency.py -v
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_DIR = BACKEND_DIR / "app"

# 「不适用」语义的所有历史别名。写入侧与各集成方都可能写入其中任意一种。
NA_ALIASES = ("na", "not_applicable", "not-applicable", "n/a")

_NA_LITERAL = re.compile(
    r"""['"](?:""" + "|".join(re.escape(a) for a in NA_ALIASES) + r""")['"]""",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# 白名单：这些位置**允许**出现多值判定，且不是"又写了一套统计"
# ---------------------------------------------------------------------------
ALLOWED_FILES = frozenset(
    {
        # 唯一权威口径来源
        "app/utils/item_stats.py",
        # API 出入参类型定义（校验白名单，不是统计实现）
        "app/schemas/record.py",
        "app/schemas/task.py",
    }
)

# ---------------------------------------------------------------------------
# 债务清单：当前仍存在的历史实现，待逐步收敛到 item_stats。
# 收敛一处 → 删除一行。**只允许减少，不允许新增。**
#
# 2026-09-17：原 6 处已全部收敛（analytics.py ×2 / tasks.py / llm_service.py /
# report_service.py / formal_audit_sync_service.py），清单归零。
# 归零后本测试即成为**纯门禁**：任何新增的口径实现点都会直接失败。
# ---------------------------------------------------------------------------
KNOWN_DEBT: frozenset[tuple[str, int]] = frozenset()


def _iter_code_lines(path: Path):
    """逐行产出 ``(行号, 代码文本)``，已剔除**注释**与**文档字符串**。

    为什么必须剔除：注释和 docstring 里经常出现「原来只认 "na"/"not_applicable"」
    这类说明文字。它们是解释，不是实现；若参与扫描就会造成误报，
    而误报会让人开始怀疑门禁、进而绕过门禁 —— 门禁一旦被绕过就等于没有。

    实现方式：用 ``tokenize`` 拿到 token 的精确列区间后原位挖空。
    注意 **只挖注释与独立成句的字符串（docstring）**，
    不能挖掉参与比较的字符串字面量 —— 那正是本扫描要检测的信号。
    """
    source = path.read_text(encoding="utf-8", errors="ignore")
    masked = source.splitlines()

    def _blank(row: int, start: int, end: int) -> None:
        idx = row - 1
        if 0 <= idx < len(masked):
            line = masked[idx]
            masked[idx] = line[:start] + " " * (end - start) + line[end:]

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        tokens = []

    # 语句起始标记：紧跟其后的字符串即 docstring / 独立字符串语句。
    # ENCODING 必须在内 —— 文件首个 token 就是 ENCODING，
    # 漏掉它会导致**模块级 docstring** 逃过挖空（实测踩过）。
    _STMT_START = {
        tokenize.ENCODING,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
    }
    prev_significant = tokenize.ENCODING

    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            _blank(tok.start[0], tok.start[1], len(masked[tok.start[0] - 1]))
        elif tok.type == tokenize.STRING and prev_significant in _STMT_START:
            (srow, scol), (erow, ecol) = tok.start, tok.end
            for row in range(srow, erow + 1):
                start = scol if row == srow else 0
                end = ecol if row == erow else len(masked[row - 1])
                _blank(row, start, end)

        if tok.type not in (
            tokenize.NL,
            tokenize.COMMENT,
            tokenize.ENCODING,
            tokenize.NEWLINE,
        ):
            prev_significant = tok.type

    return list(enumerate(masked, start=1))


def _scan_na_definition_sites() -> set[tuple[str, int, str]]:
    """扫描 app/ 下所有同时判定两个及以上「不适用」别名的代码行。"""
    sites: set[tuple[str, int, str]] = set()
    for path in sorted(APP_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(BACKEND_DIR).as_posix()
        for lineno, line in _iter_code_lines(path):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            aliases_found = {
                m.group(0).strip("'\"").lower() for m in _NA_LITERAL.finditer(line)
            }
            if len(aliases_found) >= 2:
                sites.add((rel, lineno, stripped[:120]))
    return sites


def test_no_new_na_definition_sites():
    """不得新增第 7 处「不适用」口径实现。

    失败时的处置方式（二选一）：
      * 正解：改为调用 ``app.utils.item_stats.classify_result``，
              然后把该位置从 KNOWN_DEBT 中删掉；
      * 例外：若确属类型定义/校验白名单，加入 ALLOWED_FILES。
    """
    found = _scan_na_definition_sites()
    unexpected = [
        (f, n, s)
        for f, n, s in sorted(found)
        if f not in ALLOWED_FILES and (f, n) not in KNOWN_DEBT
    ]

    assert not unexpected, (
        "检测到新的「不适用」口径实现点，这会再次造成跨端数据不一致。\n"
        "请改用 app/utils/item_stats.py 的统一口径：\n\n"
        + "\n".join(f"  {f}:{n}\n      {s}" for f, n, s in unexpected)
        + f"\n\n当前债务清单（{len(KNOWN_DEBT)} 处）：\n"
        + "\n".join(f"  {f}:{n}" for f, n in sorted(KNOWN_DEBT))
    )


def test_debt_list_has_no_stale_entries():
    """债务清单必须反映真实情况——已收敛的位置要删掉，否则清单会失真。"""
    found_pairs = {(f, n) for f, n, _ in _scan_na_definition_sites()}
    stale = sorted(KNOWN_DEBT - found_pairs)

    assert not stale, (
        "以下位置已不再存在口径实现，请从 KNOWN_DEBT 中删除，保持清单可信：\n"
        + "\n".join(f"  {f}:{n}" for f, n in stale)
    )


def test_debt_does_not_grow():
    """债务规模只减不增：当前上限 0 处（已全部收敛，成为硬门禁）。"""
    assert len(KNOWN_DEBT) <= 0, (
        f"口径债务已从 0 增长到 {len(KNOWN_DEBT)} 处。"
        "本项目已完成口径收敛，不得再引入新的口径实现点；"
        "请改为调用 app.utils.item_stats.classify_result()。"
    )


def test_item_stats_is_importable_and_covers_all_aliases():
    """权威口径模块必须覆盖全部历史别名，且能正确归类。"""
    from app.utils.item_stats import NA_VALUES, classify_result

    for alias in NA_ALIASES:
        assert alias in NA_VALUES, f"item_stats.NA_VALUES 缺少别名：{alias}"
        assert classify_result(alias) == "na", f"别名 {alias} 未被归类为 na"

    # 大小写与空白容错
    for variant in ("NA", " Not_Applicable ", "N/A"):
        assert classify_result(variant) == "na", f"变体 {variant!r} 未被正确归类"


def test_scanner_self_check(tmp_path):
    """扫描器自检：既要认出真实实现，也不能被注释/docstring 带偏。

    背景：``analytics.py`` 的模块 docstring 里写着
    「历史上工作台只认 ("na","not_applicable")、详情只认 "na"」，
    这是**说明文字**。第一版扫描器把它当成了实现点，产生误报。
    误报会让门禁失去公信力并被绕过，因此这里用正反样例把它钉死。
    """
    sample = tmp_path / "sample.py"
    sample.write_text(
        "'''说明：历史上只认 \"na\"/\"not_applicable\"，两处对不上。'''\n"
        "def f(v):\n"
        "    '''docstring 里也提 \"n/a\" 与 \"not-applicable\"。'''\n"
        "    # 注释：\"na\" / \"n/a\" 都要算不适用\n"
        "    if v in ('na', 'not_applicable'):\n"
        "        return True\n"
        "    na_count = 0  # 手写计数\n"
        "    return na_count\n",
        encoding="utf-8",
    )

    code = dict(_iter_code_lines(sample))
    # 注释被挖空
    assert "都要算不适用" not in code[4], "行内注释未被剔除"
    # docstring 被挖空
    assert "docstring" not in code[3], "函数 docstring 未被剔除"
    assert "说明" not in code[1], "模块 docstring 未被剔除"
    # 真实比较语句保留
    assert "'not_applicable'" in code[5], "真实比较字面量被误删，扫描器失明"
    # 真实手写计数保留
    assert _HANDROLL_PATTERN.search(code[7]), "手写 na_count 未被识别"


# ---------------------------------------------------------------------------
# 单字面量判定检测
# ---------------------------------------------------------------------------
# 上面的「不适用」扫描只覆盖**同时写两个别名**的行。更隐蔽的漏网形态是
# **只写一个**字面量：`result == "fail"`。库里真实存在 non_compliant /
# unqualified / "3" 等写法，只认 "fail" 就会漏计数 —— 这是「列表数字与
# 详情页对不上」最直接的来源，2026-09 已在 enterprises.py / agent_service.py /
# analytics.py / audit_projects.py 共 7 处踩到。
#
# 注意字段范围：只扫**条目级**判定字段。`overall_result` 是**记录级**结论枚举
# （pass / partial_pass / fail，partial_pass 是独立状态而非别名），
# 把它纳入会制造误报，故排除。
_RESULT_FIELD = r"(?:radio_value|result|evaluation_3level)"
_SINGLE_LITERAL = re.compile(
    r"\b"
    + _RESULT_FIELD
    + r"\s*(?:==|!=)\s*['\"](?:"
    + "|".join(re.escape(v) for v in sorted(set(NA_ALIASES) | {"pass", "fail"}))
    + r"|compliant|non_compliant|qualified|unqualified|不适用)['\"]",
    re.IGNORECASE,
)

# 合规标记：命中其一即视为已走统一口径
_LITERAL_COMPLIANT_MARKERS = (
    "classify_result",
    "classify_item",
    "classify_evaluation_3level",
    "item_stats",
    "FAIL_VALUES",
    "PASS_VALUES",
    "NA_VALUES",
    "result_in(",
    "is_pass(",
    "is_fail(",
    "is_na(",
)

# 已知的合法单字面量判定（登记在册，逐条给出理由）。
# 当前为空：条目级判定已全部收敛。
SINGLE_LITERAL_DEBT: frozenset[tuple[str, int]] = frozenset()


def _scan_single_literal_judgements() -> set[tuple[str, int, str]]:
    sites: set[tuple[str, int, str]] = set()
    for path in sorted(APP_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(BACKEND_DIR).as_posix()
        if rel in ALLOWED_FILES:
            continue
        for lineno, line in _iter_code_lines(path):
            if not _SINGLE_LITERAL.search(line):
                continue
            if any(m in line for m in _LITERAL_COMPLIANT_MARKERS):
                continue
            sites.add((rel, lineno, line.strip()[:120]))
    return sites


def test_no_single_literal_result_judgement():
    """条目级判定不得只认单一字面量。

    正解：改用 ``classify_result`` / ``classify_item``（Python 侧）
    或 ``result_in(col, "fail")``（SQL 侧），使其覆盖全部历史与集成别名。
    """
    found = _scan_single_literal_judgements()
    unexpected = [
        (f, n, s) for f, n, s in sorted(found) if (f, n) not in SINGLE_LITERAL_DEBT
    ]

    assert not unexpected, (
        "检测到条目级判定只认单一字面量，会漏掉历史/集成写入的同义值：\n"
        + "\n".join(f"  {f}:{n}\n      {s}" for f, n, s in unexpected)
        + "\n\n请改用 app.utils.item_stats 的统一口径：\n"
        "  · Python 侧：classify_result(v) / classify_item(obj)\n"
        '  · SQL 侧  ：col.in_(sorted(FAIL_VALUES)) 或 result_in(col, "fail")\n'
    )


def test_single_literal_scanner_self_check(tmp_path):
    """扫描器自检：必须认出裸字面量判定，且不误报统一口径写法。"""
    sample = tmp_path / "sample2.py"
    sample.write_text(
        "def f(items, col):\n"
        "    bad1 = [i for i in items if i.result == 'fail']\n"
        "    bad2 = [i for i in items if i.radio_value == 'not_applicable']\n"
        "    ok1 = [i for i in items if classify_result(i.result) == 'fail']\n"
        "    ok2 = col.in_(sorted(FAIL_VALUES))\n"
        "    ok3 = [i for i in items if i.evaluation_3level == '3']\n"
        "    return bad1, bad2, ok1, ok2, ok3\n",
        encoding="utf-8",
    )

    flagged = {
        lineno
        for lineno, line in _iter_code_lines(sample)
        if _SINGLE_LITERAL.search(line)
        and not any(m in line for m in _LITERAL_COMPLIANT_MARKERS)
    }
    assert flagged == {2, 3}, f"扫描器识别异常，命中行号={sorted(flagged)}，期望 [2, 3]"


# ---------------------------------------------------------------------------
# 手写 na 计数检测
# ---------------------------------------------------------------------------
# 合规写法：从统一口径取值，如 `na_count = _stats['na']` / `na_count = stats.get("na")`
# 或直接按统一归类函数推导，如 `sum(1 for i in items if classify_result(...) == "na")`
_COMPLIANT_MARKERS = (
    "item_stats",
    "_stats",
    "calculate_item_stats",
    "classify_result",
)
_HANDROLL_PATTERN = re.compile(r"na_count\s*(?:\+=|=)", re.IGNORECASE)

# 已知的手写实现 —— 均属**待修复缺陷**，收敛后请删除对应行。
# 2026-09-17：原 3 处（records.py ×2 / report_service.py ×1）已全部收敛，清单归零。
HANDROLL_DEBT: frozenset[tuple[str, int]] = frozenset()


def _scan_handrolled_na_counting() -> set[tuple[str, int, str]]:
    sites: set[tuple[str, int, str]] = set()
    scan_targets = [
        APP_DIR / "routers" / "records.py",
        APP_DIR / "services" / "report_service.py",
        APP_DIR / "routers" / "tasks.py",
        APP_DIR / "routers" / "analytics.py",
    ]
    for path in scan_targets:
        if not path.exists():
            continue
        rel = path.relative_to(BACKEND_DIR).as_posix()
        for lineno, line in _iter_code_lines(path):
            if not _HANDROLL_PATTERN.search(line):
                continue
            if any(marker in line for marker in _COMPLIANT_MARKERS):
                continue  # 从统一口径取值，合规
            sites.add((rel, lineno, line.strip()[:120]))
    return sites


def test_no_new_handrolled_na_counting():
    """不得新增手写的 na 计数实现——这是「报告数字对不上」的直接来源。"""
    found = _scan_handrolled_na_counting()
    unexpected = [
        (f, n, s) for f, n, s in sorted(found) if (f, n) not in HANDROLL_DEBT
    ]

    assert not unexpected, (
        "检测到新的手写 na 计数实现：\n"
        + "\n".join(f"  {f}:{n}\n      {s}" for f, n, s in unexpected)
        + "\n\n请改用 app.utils.item_stats.calculate_item_stats()。"
    )


def test_handrolled_na_counting_debt_is_tracked():
    """手写实现必须全部登记在册——漏登记意味着有未被发现的统计分叉。"""
    found_pairs = {(f, n) for f, n, _ in _scan_handrolled_na_counting()}
    untracked = sorted(found_pairs - HANDROLL_DEBT)
    stale = sorted(HANDROLL_DEBT - found_pairs)

    assert not untracked, (
        "以下手写统计未登记到 HANDROLL_DEBT，请确认并登记：\n"
        + "\n".join(f"  {f}:{n}" for f, n in untracked)
    )
    assert not stale, (
        "以下位置已收敛，请从 HANDROLL_DEBT 中删除：\n"
        + "\n".join(f"  {f}:{n}" for f, n in stale)
    )
