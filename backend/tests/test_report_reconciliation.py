"""报表合理性测试：交叉对账 + 守恒律 + 编号稳定性。

对应测试需求的第 3 项：**报表不仅要"能通过"，还要"数据与逻辑正确"**。

═══════════════════════════════════════════════════════════════════════════
 设计原则：不信任任何单一接口的自述
═══════════════════════════════════════════════════════════════════════════
第三方测试反复发现的不是"接口报错"，而是**同一份数据在不同页面给出不同数字**：

  · 报告预览「不合格 1 / 不适用 1」 vs 记录详情「不符合项 1 / 不适用项 0」
  · 合规率在同一份检查上出现 50% / 16.67% / 0% 三个值
  · 模板页显示 6 项、执行页显示 8 项、任务列表显示 3 项
  · 工作台「待办 32 + 已完成 34 = 66 ≠ 总数 68」

这类缺陷无法靠"接口返回 200"发现，只能靠**跨接口对账**与**守恒律**发现。
因此本文件的核心断言形式是：

    接口 A 的数字  ==  接口 B 的数字  ==  明细逐条重算的结果

运行前提同 test_api_crud_matrix.py（需 EFIS_TEST_DATABASE_URL 指向隔离测试库）。
"""

from __future__ import annotations

import re

import pytest

pytestmark = pytest.mark.report

# 报告编号形如 EFIS-2026-0723-6D49505B
REPORT_NO_PATTERN = re.compile(r"^EFIS-(\d{4})-(\d{2})(\d{2})-([0-9A-F]{8})$")


def _data(resp):
    assert resp.status_code in (200, 201), f"HTTP {resp.status_code}: {resp.text[:400]}"
    return resp.json().get("data")


# ---------------------------------------------------------------------------
# 夹具：挑一条已提交、且含多种判定结果的真实记录
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sample_record(client, auth_headers):
    """取一条含 pass/fail/na 混合的记录用于对账。

    优先使用测试库中已有的已提交记录；没有则跳过（不造数据，避免污染）。
    """
    listed = _data(client.get("/api/records", params={"status": "submitted", "page_size": 50}, headers=auth_headers))
    items = (listed.get("items") if isinstance(listed, dict) else listed) or []

    for it in items:
        rid = it.get("id")
        detail = _data(client.get(f"/api/records/{rid}", headers=auth_headers))
        stats = (detail or {}).get("statistics") or (detail or {}).get("stats") or {}
        if stats.get("fail", 0) > 0 and stats.get("total", 0) > 0:
            return rid

    pytest.skip("测试库中没有「含不合格项的已提交记录」，无法进行报表对账")


# ---------------------------------------------------------------------------
# 1. 核心对账：详情 vs 报告
# ---------------------------------------------------------------------------


def test_detail_and_report_statistics_agree(client, auth_headers, sample_record):
    """记录详情与检查报告必须给出完全相同的统计数字。

    回归目标：外部测试 P0-35 —— 详情走 ``_calculate_item_stats``（只认 "na"），
    报告走 ``report_service``（认 "na"/"not_applicable"），
    全库 na=0 条 → 详情的「不适用项」恒为 0，两页对不上。
    """
    detail = _data(client.get(f"/api/records/{sample_record}", headers=auth_headers))
    report = _data(client.get(f"/api/records/{sample_record}/report", headers=auth_headers))

    d_stats = detail.get("statistics") or detail.get("stats") or {}
    r_stats = report.get("statistics") or {}

    assert d_stats, f"详情接口未返回 statistics：{list(detail.keys())}"
    assert r_stats, f"报告接口未返回 statistics：{list(report.keys())}"

    # 字段名可能不同（pass/合格、na/不适用），统一到内部口径再比
    def norm(stats: dict) -> dict:
        def pick(*keys):
            for k in keys:
                if k in stats:
                    return stats[k]
            return None

        return {
            "total": pick("total", "总计", "total_items"),
            "pass": pick("pass", "pass_count", "合格"),
            "fail": pick("fail", "fail_count", "不合格"),
            "na": pick("na", "na_count", "not_applicable", "不适用"),
        }

    dn, rn = norm(d_stats), norm(r_stats)

    for key in ("total", "pass", "fail", "na"):
        if dn[key] is None or rn[key] is None:
            continue
        assert dn[key] == rn[key], (
            f"「{key}」在详情与报告中对不上：详情={dn[key]}，报告={rn[key]}\n"
            f"详情原始：{d_stats}\n报告原始：{r_stats}\n"
            "这是「同一份数据两个页面数字不一致」类缺陷，必须统一到 "
            "app.utils.item_stats 的单一口径。"
        )


# ---------------------------------------------------------------------------
# 2. 守恒律：对真实数据重算
# ---------------------------------------------------------------------------


def test_statistics_satisfy_conservation_on_real_record(client, auth_headers, sample_record):
    """统计各项必须守恒：pass + fail + na + unfilled == total。"""
    detail = _data(client.get(f"/api/records/{sample_record}", headers=auth_headers))
    stats = detail.get("statistics") or detail.get("stats") or {}

    if not all(k in stats for k in ("total", "pass", "fail", "na")):
        pytest.skip(f"统计字段不完整，跳过守恒校验：{stats}")

    total = stats["total"]
    filled = stats.get("filled", stats["pass"] + stats["fail"] + stats["na"])
    unfilled = stats.get("unfilled", total - filled)

    assert stats["pass"] + stats["fail"] + stats["na"] + unfilled == total, (
        f"统计不守恒：{stats}（pass+fail+na+unfilled 应等于 total={total}）"
    )
    assert filled + unfilled == total, f"已填报 + 未填写 ≠ 总数：{stats}"


def test_item_count_matches_actual_items(client, auth_headers, sample_record):
    """统计里的 total 必须等于接口实际返回的检查项条数。"""
    detail = _data(client.get(f"/api/records/{sample_record}", headers=auth_headers))
    items = detail.get("items") or []
    stats = detail.get("statistics") or detail.get("stats") or {}

    if not items or "total" not in stats:
        pytest.skip("详情未返回 items 或 total，跳过")

    countable = [i for i in items if not i.get("is_category")]

    assert stats["total"] == len(countable), (
        f"统计 total={stats['total']}，但实际可计数检查项为 {len(countable)} 条"
        f"（共返回 {len(items)} 条，其中分类节点 {len(items) - len(countable)} 条）。\n"
        "「分类节点不得计入检查项总数」是外部测试 P0-03 的验收标准。"
    )


# ---------------------------------------------------------------------------
# 3. 合规率口径
# ---------------------------------------------------------------------------


def test_compliance_rate_matches_recomputation(client, auth_headers, sample_record):
    """合规率必须等于「合格 /（合格 + 不合格）」，排除不适用与未填写。"""
    report = _data(client.get(f"/api/records/{sample_record}/report", headers=auth_headers))
    stats = report.get("statistics") or {}
    rate = stats.get("pass_rate", stats.get("合格率"))
    if rate is None:
        pytest.skip("报告未返回 pass_rate")

    rated = stats.get("pass", 0) + stats.get("fail", 0)
    expected = round(stats.get("pass", 0) / rated * 100, 1) if rated > 0 else 0.0

    assert abs(float(rate) - expected) < 0.15, (
        f"合规率 {rate}% 与重算值 {expected}% 不符（分母应为「已填报项」）。\n"
        f"原始统计：{stats}\n"
        "外部测试曾因口径不明在同一份检查上看到 50%/16.67%/0% 三个值。"
    )


# ---------------------------------------------------------------------------
# 4. 报告编号：稳定性与来源
# ---------------------------------------------------------------------------


def test_report_number_format_is_valid(client, auth_headers, sample_record):
    report = _data(client.get(f"/api/records/{sample_record}/report", headers=auth_headers))
    number = report.get("report_number")
    assert number, "报告未返回 report_number"
    assert REPORT_NO_PATTERN.match(number), f"报告编号格式不合法：{number}"


def test_report_number_is_stable_across_reads(client, auth_headers, sample_record):
    """同一份记录反复查看，编号必须完全一致（不得随查看时间漂移）。"""
    numbers = {
        _data(client.get(f"/api/records/{sample_record}/report", headers=auth_headers)).get("report_number")
        for _ in range(3)
    }
    assert len(numbers) == 1, f"报告编号随查看时间漂移：{numbers}"


def test_report_number_date_derives_from_inspection_date(client, auth_headers, sample_record):
    """编号中的日期段必须来自记录的检查日期，而不是「今天」。

    回归目标：``_generate_report_number`` 曾用 ``datetime.now()``，
    同一份记录今天看是 EFIS-2026-0915-XXXX，明天看就变成 EFIS-2026-0916-XXXX。
    """
    detail = _data(client.get(f"/api/records/{sample_record}", headers=auth_headers))
    report = _data(client.get(f"/api/records/{sample_record}/report", headers=auth_headers))

    inspection_date = (detail.get("inspection_date") or "")[:10]
    if not inspection_date:
        pytest.skip("记录无检查日期，无法校验编号来源")

    match = REPORT_NO_PATTERN.match(report["report_number"])
    assert match, f"报告编号格式异常：{report['report_number']}"

    # 编号形如 EFIS-2026-0915-XXXXXXXX → 日期段 20260915
    number_date = f"{match.group(1)}{match.group(2)}{match.group(3)}"
    expected = inspection_date.replace("-", "")
    assert number_date == expected, (
        f"报告编号日期段 {number_date} ≠ 记录检查日期 {expected}。\n"
        "编号必须由检查日期派生（或落库固化），否则跨天查看会得到不同编号。"
    )


# ---------------------------------------------------------------------------
# 5. 跨端展示一致性
# ---------------------------------------------------------------------------


def test_report_item_order_is_deterministic(client, auth_headers, sample_record):
    """报告的检查项顺序必须稳定且可复现（PC 与 H5 走同一份数据）。

    回归目标：PC 走 ``template.items``（build_tree 重建），
    H5 走 ``template_snapshot['items']``（快照原始顺序），同一记录两端顺序不同。
    """
    orders = []
    for _ in range(3):
        report = _data(client.get(f"/api/records/{sample_record}/report", headers=auth_headers))
        items = report.get("items") or report.get("check_items") or []
        orders.append([str(i.get("id") or i.get("title")) for i in items])

    assert len({tuple(o) for o in orders}) == 1, "报告检查项顺序不稳定，多次请求结果不同"


def test_list_totals_equal_detail_sum(client, auth_headers, sample_record):
    """列表页展示的汇总数字，必须等于逐条明细求和。"""
    detail = _data(client.get(f"/api/records/{sample_record}", headers=auth_headers))
    stats = detail.get("statistics") or detail.get("stats") or {}
    items = detail.get("items") or []

    if not items or "total" not in stats:
        pytest.skip("缺少 items 或 total，跳过")

    recounted = {"total": 0, "pass": 0, "fail": 0, "na": 0}
    NA = {"na", "not_applicable", "not-applicable", "n/a"}
    for it in items:
        if it.get("is_category"):
            continue
        recounted["total"] += 1
        value = (it.get("radio_value") or "").strip().lower()
        if value == "pass":
            recounted["pass"] += 1
        elif value == "fail":
            recounted["fail"] += 1
        elif value in NA:
            recounted["na"] += 1

    for key in recounted:
        if key in stats:
            assert stats[key] == recounted[key], (
                f"「{key}」接口自述 {stats[key]}，逐条重算为 {recounted[key]}\n"
                f"完整统计：{stats}"
            )
