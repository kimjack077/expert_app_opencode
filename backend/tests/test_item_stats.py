"""单元层测试：检查项统计口径的纯逻辑。

覆盖三类"报表合理性"的底层正确性，全部为纯函数，无需数据库：

1. **守恒律** —— 各分项之和必须等于总数，不允许出现"凭空多出/丢失"的条目；
2. **归类完备性** —— 所有历史别名、脏数据、空值都必须落入确定的分支，
   不能出现"既不算合格也不算不合格"的黑洞；
3. **合规率口径** —— 分母必须排除「不适用」与「未填写」，这是第三方
   反复质疑的点（同一份检查出现过 50% / 16.67% / 0% 三个值）。

运行::

    .venv\\Scripts\\python.exe -m pytest tests/test_item_stats.py -v
"""

from __future__ import annotations

import pytest

from app.utils.item_stats import (
    EVAL3_FAIL_VALUES,
    EVAL3_PASS_VALUES,
    FAIL_VALUES,
    NA_VALUES,
    OTHER_VALUES,
    PASS_VALUES,
    RESULT_FIELDS,
    calculate_item_stats,
    classify_evaluation_3level,
    classify_item,
    classify_result,
    compliance_rate,
    is_fail,
    is_na,
    is_pass,
    result_in,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1. 归类完备性
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", sorted(PASS_VALUES))
def test_pass_aliases_are_classified(value):
    assert classify_result(value) == "pass"


@pytest.mark.parametrize("value", sorted(FAIL_VALUES))
def test_fail_aliases_are_classified(value):
    assert classify_result(value) == "fail"


@pytest.mark.parametrize("value", sorted(NA_VALUES))
def test_na_aliases_are_classified(value):
    assert classify_result(value) == "na"


@pytest.mark.parametrize("value", [None, "", "   ", 0, "unknown", "待整改"])
def test_unknown_values_do_not_raise_and_return_none(value):
    """脏数据不得抛异常——生产库实测存在 NULL / 空串等取值。"""
    assert classify_result(value) is None


@pytest.mark.parametrize("value", sorted(OTHER_VALUES))
def test_intermediate_states_are_not_forced_into_buckets(value):
    """「待整改 / 观察项」是中间态，不得被算成合格或不合格。"""
    assert classify_result(value) is None, (
        f"{value} 属于中间态，不应落入 pass/fail/na 任一桶，"
        "否则会导致统计数字虚高"
    )


def test_classification_is_case_and_whitespace_tolerant():
    assert classify_result("  PASS ") == "pass"
    assert classify_result("Not_Applicable") == "na"
    assert classify_result("FAIL\n") == "fail"


# ---------------------------------------------------------------------------
# 2. 守恒律
# ---------------------------------------------------------------------------


def _items(*values):
    return [{"radio_value": v} for v in values]


def _fake_column(name: str = "radio_value"):
    """构造一个真实 SQLAlchemy 列，用于校验 SQL 侧判定的实际渲染结果。"""
    from sqlalchemy import Column, String

    return Column(name, String)


def test_total_equals_sum_of_buckets():
    """核心守恒律：total == pass + fail + na + observe + unfilled。

    2026-09-18 修订：新增 ``observe``（观察项/待整改）一档。
    旧契约把 observe 算进 ``unfilled``，导致
    「合格 + 不合格 + 不适用」恒小于 total，报告汇总表出现对不上的缺口。
    """
    items = _items("pass", "fail", "na", "not_applicable", None, "", "observe", "pass")
    stats = calculate_item_stats(items)

    assert stats["total"] == len(items)
    assert (
        stats["pass"]
        + stats["fail"]
        + stats["na"]
        + stats["observe"]
        + stats["unfilled"]
        == stats["total"]
    ), f"统计不守恒：{stats}"


def test_observe_is_filled_not_unfilled():
    """回归：观察项是「已填写」，不得被统计成「未填报」。

    外部复测 bug：一记录 4 项 = 1 合格 + 2 观察项 + 1 不适用，
    报告汇总显示「1 合格 + 0 不合格 + 1 不适用 = 2」而「总计 4」，
    差额 2 项无处归属——根因就是 observe 被塞进了 unfilled。
    """
    stats = calculate_item_stats(_items("pass", "observe", "observe", "na"))

    assert stats["total"] == 4
    assert stats["observe"] == 2
    assert stats["unfilled"] == 0, "观察项必须是已填写，不能计入未填报"
    assert stats["filled"] == 4
    assert stats["pass"] + stats["fail"] + stats["na"] + stats["observe"] == stats["total"]


def test_classify_result_ext_bucket_names_are_all_valid_stats_keys():
    """防回归：classify_result_ext 的返回值必须是 calculate_item_stats 的合法键。

    事故背景：该函数曾返回 "other"，而统计字典的键是 "observe"，
    `stats[bucket] += 1` 直接抛 KeyError，把 /api/records/{id}/report 打成 500。
    任何新增桶都必须同时出现在统计字典里。
    """
    from app.utils.item_stats import classify_result_ext

    valid_keys = set(calculate_item_stats([]).keys())
    for raw in ("pass", "fail", "na", "not_applicable", "observe", "pending_rectification", "", None):
        bucket = classify_result_ext(raw)
        assert bucket is None or bucket in valid_keys, (
            f"classify_result_ext({raw!r}) 返回了非法桶名 {bucket!r}，"
            f"合法键为 {sorted(valid_keys)}"
        )


def test_filled_plus_unfilled_equals_total():
    for case in (
        _items("pass", "fail"),
        _items("pass", None),
        _items(),
        _items(None, None, None),
        _items("na", "na", "na"),
    ):
        stats = calculate_item_stats(case)
        assert stats["filled"] + stats["unfilled"] == stats["total"], stats


def test_empty_and_none_input_are_safe():
    for empty in (None, [], ()):
        stats = calculate_item_stats(empty)
        # 契约变更（2026-09-18）：新增 observe 桶，用于让
        # 「pass + fail + na + observe + unfilled == total」在汇总表上闭合。
        assert stats == {
            "total": 0,
            "pass": 0,
            "fail": 0,
            "na": 0,
            "observe": 0,
            "filled": 0,
            "unfilled": 0,
        }


def test_supports_both_orm_objects_and_dicts():
    class FakeItem:
        def __init__(self, value):
            self.radio_value = value

    stats = calculate_item_stats([FakeItem("pass"), FakeItem("fail"), {"radio_value": "na"}])
    assert (stats["pass"], stats["fail"], stats["na"]) == (1, 1, 1)


def test_real_world_record_regression():
    """回归：外部测试记录 9a083a0f 的实际构成。

    4 个检查项 = 1 不合格 + 1 不适用 + 2 未填写（radio_value 为空，
    但被误写了 numeric/text 值）。修复前「不适用」恒为 0，与报告对不上。
    """
    items = _items("fail", "not_applicable", None, None)
    stats = calculate_item_stats(items)

    assert stats == {
        "total": 4,
        "pass": 0,
        "fail": 1,
        "na": 1,
        "observe": 0,
        "filled": 2,
        "unfilled": 2,
    }


# ---------------------------------------------------------------------------
# 3. 合规率口径
# ---------------------------------------------------------------------------


def test_compliance_rate_excludes_na_and_unfilled():
    """合格 3 / 不合格 1 / 不适用 2 → 合规率必须是 75%，不是 50% 也不是 16.67%。"""
    stats = calculate_item_stats(_items("pass", "pass", "pass", "fail", "na", "not_applicable"))
    assert stats["na"] == 2
    assert compliance_rate(stats) == 75.0, (
        "合规率分母必须排除「不适用」与「未填写」。"
        "第三方测试曾因口径不明看到 50%/16.67%/0% 三个互相矛盾的值。"
    )


def test_compliance_rate_is_zero_when_nothing_rated():
    """全部未填写 / 全部不适用时，不得除零，也不得给出误导性的 100%。"""
    assert compliance_rate(calculate_item_stats(_items(None, None))) == 0.0
    assert compliance_rate(calculate_item_stats(_items("na", "na"))) == 0.0
    assert compliance_rate(calculate_item_stats([])) == 0.0


def test_compliance_rate_bounds():
    stats = calculate_item_stats(_items(*(["pass"] * 100)))
    assert compliance_rate(stats) == 100.0

    stats = calculate_item_stats(_items(*(["fail"] * 100)))
    assert compliance_rate(stats) == 0.0


# ---------------------------------------------------------------------------
# 4. 跨模型归类（三套并行记录模型的唯一入口）
# ---------------------------------------------------------------------------
# 背景：InspectionRecordItem / TaskItemRecord / AuditAreaRecord 三套模型
# 判定字段名不同（radio_value / result / evaluation_3level）。
# 旧代码在 audit_projects.py 用 `result == "pass" or evaluation_3level in {"1","2"}`
# 这种 `or` 组合，会让同一条目**同时计入合格与不合格**。


def test_evaluation_3level_basic_compliant_counts_as_pass():
    """「2 基本符合」必须算合格——这是与 classify_result 的唯一差别。

    若误把三级评价并入 PASS_VALUES，radio_value="2" 会被错判为合格；
    若漏掉 "2"，审核项目的合格数会凭空少一截。
    """
    assert classify_evaluation_3level("1") == "pass"
    assert classify_evaluation_3level("2") == "pass"
    assert classify_evaluation_3level("3") == "fail"
    assert classify_evaluation_3level(None) is None
    assert classify_evaluation_3level("") is None
    assert classify_evaluation_3level("9") is None

    # 边界：classify_result 不认 "2"，两者不可互相替代
    assert classify_result("2") is None
    assert classify_result("1") == "pass"


def test_classify_item_prefers_radio_value_then_result():
    """字段优先级：radio_value → result → evaluation_3level。"""
    assert classify_item({"radio_value": "pass", "result": "fail"}) == "pass"
    assert classify_item({"radio_value": None, "result": "fail"}) == "fail"
    assert classify_item({"radio_value": "", "result": "fail"}) == "fail"
    assert classify_item({"result": "fail", "evaluation_3level": "1"}) == "fail"
    assert classify_item({"evaluation_3level": "3"}) == "fail"
    assert classify_item({"evaluation_3level": "2"}) == "pass"
    assert classify_item({}) is None
    assert classify_item({"radio_value": None, "result": "", "evaluation_3level": None}) is None


def test_classify_item_never_double_counts():
    """一条明细只能落进一个桶——旧实现的 `or` 组合会让 pass/fail 同时 +1。"""
    for combo in (
        {"radio_value": "pass", "evaluation_3level": "3"},
        {"result": "fail", "evaluation_3level": "1"},
        {"radio_value": "not_applicable", "result": "pass"},
    ):
        buckets = [classify_item(combo) for _ in range(1)]
        assert len(buckets) == 1, f"{combo} 产生了多个归类：{buckets}"


def test_classify_item_supports_orm_objects():
    """必须同时支持 ORM 对象与 dict —— 报告装配路径传的是 dict。"""

    class _Row:
        radio_value = None
        result = "fail"
        evaluation_3level = None

    assert classify_item(_Row()) == "fail"
    assert classify_item({"result": "fail"}) == "fail"


def test_classify_item_handles_real_db_values():
    """用真实库中出现的取值回归——这些是探查生产数据得到的事实，不是猜测。

    radio_value: pass(264) / None(204) / fail(16) / not_applicable(7) /
                 observe(3) / ''(2) / pending_rectification(1)
    result     : None(317) / pass(159) / fail(11) / ''(6) / na(4)
    """
    real_radio_values = [
        "pass",
        "fail",
        "not_applicable",
        "observe",
        "",
        "pending_rectification",
        None,
    ]
    real_results = ["pass", "fail", "na", "", None]

    for value in real_radio_values:
        bucket = classify_item({"radio_value": value})
        assert bucket in {"pass", "fail", "na", None}, f"{value!r} 归类异常：{bucket}"

    for value in real_results:
        bucket = classify_item({"result": value})
        assert bucket in {"pass", "fail", "na", None}, f"{value!r} 归类异常：{bucket}"

    # 关键事实：两列对「不适用」的写法不同，统一口径必须都能认
    assert classify_item({"radio_value": "not_applicable"}) == "na"
    assert classify_item({"result": "na"}) == "na"


def test_is_helpers_match_classify_result():
    for value in sorted(PASS_VALUES):
        assert is_pass(value) and not is_fail(value) and not is_na(value)
    for value in sorted(FAIL_VALUES):
        assert is_fail(value) and not is_pass(value) and not is_na(value)
    for value in sorted(NA_VALUES):
        assert is_na(value) and not is_pass(value) and not is_fail(value)
    for value in sorted(OTHER_VALUES) + [None, "", "未知值"]:
        assert not is_pass(value) and not is_fail(value) and not is_na(value)


def _render(expr) -> str:
    """把 SQLAlchemy 表达式渲染成带字面量的 SQL。

    默认渲染会把 ``IN`` 的值折叠成绑定参数（``__[POSTCOMPILE_...]``），
    看不到实际别名，因此必须开 ``literal_binds``。
    """
    from sqlalchemy.dialects import postgresql

    return str(
        expr.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


def test_result_in_builds_in_clause_over_all_aliases():
    """SQL 侧判定必须展开成 IN 全别名集合，不能退化成等值比较。"""
    rendered = _render(result_in(_fake_column(), "fail"))
    assert " IN " in rendered.upper(), f"未生成 IN 子句：{rendered}"
    for alias in FAIL_VALUES:
        assert alias in rendered, f"IN 子句缺少别名 {alias!r}：{rendered}"

    rendered_na = _render(result_in(_fake_column(), "na"))
    for alias in NA_VALUES:
        assert alias in rendered_na, f"IN 子句缺少别名 {alias!r}：{rendered_na}"

    rendered_pass = _render(result_in(_fake_column(), "pass"))
    for alias in PASS_VALUES:
        assert alias in rendered_pass, f"IN 子句缺少别名 {alias!r}：{rendered_pass}"


def test_result_in_rejects_unknown_bucket():
    with pytest.raises(ValueError):
        result_in(_fake_column(), "unknown")


def test_result_fields_priority_is_declared():
    """字段优先级是契约的一部分，不得被随意重排。"""
    assert RESULT_FIELDS == ("radio_value", "result", "evaluation_3level")
