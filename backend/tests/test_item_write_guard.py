"""单元层测试：检查项写入侧校验。

对应第三方反复报出的两类问题：

1. **数据无法录入** —— 结果写进了 ``check_type`` 不匹配的字段，
   接口返回成功、库里也有值，但界面与报告读的是另一个字段，
   用户看到的是"填了没反应"。
2. **结论缺失** —— ``radio_value`` 写入了选项范围外的值，
   无法归类为合格/不合格/不适用，统计里变成「黑洞」。

全部为纯函数，无需数据库::

    .venv\\Scripts\\python.exe -m pytest tests/test_item_write_guard.py -v
"""

from __future__ import annotations

import pytest

from app.utils.item_write_guard import (
    CHECK_TYPE_RESULT_FIELD,
    RESULT_PAYLOAD_FIELDS,
    option_values,
    validate_item_payload,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1. result_options 宽容解析（库中真实存在三种形态）
# ---------------------------------------------------------------------------


def test_option_values_reads_wrapped_dict_shape():
    """形态一：{"options": [{"value": "pass", "label": "合格"}]}（库中 104 条）"""
    assert option_values(
        {"options": [{"value": "pass", "label": "合格"}, {"value": "na", "label": "不适用"}]}
    ) == ["pass", "na"]


def test_option_values_reads_bare_list_shape():
    """形态二：[{"label": "符合", "value": "pass", "color": "green"}]（库中 3 条）"""
    assert option_values(
        [
            {"label": "符合", "value": "pass", "color": "green"},
            {"label": "不符合", "value": "fail", "color": "red"},
        ]
    ) == ["pass", "fail"]


def test_option_values_tolerates_unknown_shapes():
    """未识别的结构必须 **fail-open**（返回空 = 不校验取值）。

    反面教材：若把扁平 dict 当"键即取值"映射，``{"unknown_key": 1}`` 会被解析成
    ``allowed=["unknown_key"]``，于是正常写入 ``radio_value="pass"`` 反被拒绝 ——
    那正是本模块要消除的「数据无法录入」。宁可少校验，不可误拒绝。
    """
    assert option_values(None) == []
    assert option_values({}) == []
    assert option_values([]) == []
    assert option_values({"unknown_key": 1}) == []
    assert option_values(123) == []
    assert option_values(True) == []
    # 扁平映射不属于实测形态（库中 232 条只有 3 种结构），同样 fail-open
    assert option_values({"pass": "合格", "fail": "不合格"}) == []
    # 已知的字符串列表形态仍然可用
    assert option_values(["pass", "fail"]) == ["pass", "fail"]


def test_unknown_option_shape_does_not_block_valid_write():
    """回归：未识别结构下，合法取值必须仍能写入（不得误拒）。"""
    assert (
        validate_item_payload(
            check_type="radio",
            payload={"radio_value": "pass"},
            result_options={"unknown_key": 1},
        )
        == []
    )


# ---------------------------------------------------------------------------
# 2. 字段白名单：类型与写入字段必须匹配
# ---------------------------------------------------------------------------


def test_radio_item_rejects_text_field():
    """核心用例：单选检查项把结果写进 text_value 必须被拒绝。

    这是「数据无法录入」的真实成因 —— 接口原先返回 200，
    数据落在 text_value，而 PC 端与报告只读 radio_value。
    """
    errors = validate_item_payload(
        check_type="radio",
        payload={"text_value": "符合要求"},
    )
    assert errors, "单选检查项写入 text_value 必须被拒绝"
    assert "radio_value" in errors[0], "错误信息必须指出应该写入哪个字段"
    assert "text_value" in errors[0]


def test_radio_item_rejects_numeric_field():
    errors = validate_item_payload(check_type="radio", payload={"numeric_value": "12"})
    assert errors and "radio_value" in errors[0]


def test_numeric_item_rejects_radio_field():
    errors = validate_item_payload(check_type="numeric", payload={"radio_value": "pass"})
    assert errors and "numeric_value" in errors[0]


@pytest.mark.parametrize(
    ("check_type", "field"),
    [(k, v) for k, v in CHECK_TYPE_RESULT_FIELD.items()],
)
def test_matching_field_is_accepted(check_type, field):
    """类型与字段匹配时必须放行 —— 否则正常录入会被误伤。"""
    sample = {
        "score_value": "85",
        "radio_value": "pass",
        "multi_value": ["a"],
        "numeric_value": "12.5",
        "text_value": "正常",
        "photos": ["/uploads/test.jpg"],
    }[field]
    assert validate_item_payload(check_type=check_type, payload={field: sample}) == []


def test_audit_3level_uses_radio_value():
    """三级评估复用 radio_value —— 这是模板模型的既定约定，不是笔误。"""
    assert CHECK_TYPE_RESULT_FIELD["audit_3level"] == "radio_value"


def test_unknown_check_type_is_rejected():
    """未知 check_type 必须拒绝：写入后结果落在无人读取的字段上。"""
    errors = validate_item_payload(check_type="rating", payload={"radio_value": "pass"})
    assert errors
    assert "rating" in errors[0]
    assert "radio" in errors[0], "错误信息应列出允许的类型"


def test_missing_check_type_and_empty_payload_passes():
    """未提供 check_type 且未写入任何结果 —— 允许（分步保存场景）。"""
    assert validate_item_payload(check_type=None, payload={}) == []
    assert validate_item_payload(check_type="radio", payload={}) == []


def test_none_values_are_treated_as_absent():
    """值为 None 视为未提供，不得误判为"写错字段"。"""
    assert (
        validate_item_payload(
            check_type="radio",
            payload={f: None for f in RESULT_PAYLOAD_FIELDS} | {"radio_value": "pass"},
        )
        == []
    )


def test_empty_string_is_treated_as_absent():
    assert validate_item_payload(check_type="radio", payload={"text_value": ""}) == []
    assert validate_item_payload(check_type="radio", payload={"multi_value": []}) == []


# ---------------------------------------------------------------------------
# 3. 取值合法性
# ---------------------------------------------------------------------------


def test_radio_value_outside_options_is_rejected():
    """取值越界必须拒绝并列出可选值 —— 否则该检查项在统计里变成黑洞。"""
    errors = validate_item_payload(
        check_type="radio",
        payload={"radio_value": "qualified"},
        result_options={
            "options": [
                {"value": "pass", "label": "合格"},
                {"value": "fail", "label": "不合格"},
            ]
        },
    )
    assert errors
    assert "qualified" in errors[0]
    assert "pass" in errors[0] and "fail" in errors[0], "错误信息应列出可选值"


def test_radio_value_within_options_passes():
    assert (
        validate_item_payload(
            check_type="radio",
            payload={"radio_value": "pass"},
            result_options={"options": [{"value": "pass"}, {"value": "fail"}]},
        )
        == []
    )


def test_radio_value_not_validated_when_no_options_configured():
    """库中 125 条模板项没有选项配置，此时不得拒绝任何取值。"""
    assert validate_item_payload(check_type="radio", payload={"radio_value": "anything"}) == []


def test_multi_value_must_be_list():
    errors = validate_item_payload(check_type="multi_check", payload={"multi_value": "a,b"})
    assert errors and "数组" in errors[0]


def test_multi_value_unknown_option_is_rejected():
    errors = validate_item_payload(
        check_type="multi_check",
        payload={"multi_value": ["a", "zzz"]},
        result_options=[{"value": "a"}, {"value": "b"}],
    )
    assert errors and "zzz" in errors[0]


def test_numeric_value_must_be_number():
    errors = validate_item_payload(check_type="numeric", payload={"numeric_value": "约 12 米"})
    assert errors and "不是合法数字" in errors[0]


def test_numeric_value_respects_min_max():
    assert (
        validate_item_payload(
            check_type="numeric", payload={"numeric_value": "5"}, min_value=0, max_value=10
        )
        == []
    )
    assert validate_item_payload(
        check_type="numeric", payload={"numeric_value": "-1"}, min_value=0, max_value=10
    )
    assert validate_item_payload(
        check_type="numeric", payload={"numeric_value": "11"}, min_value=0, max_value=10
    )


def test_score_value_must_be_number():
    errors = validate_item_payload(check_type="score", payload={"score_value": "优秀"})
    assert errors and "不是合法数字" in errors[0]


def test_text_value_length_limit():
    assert validate_item_payload(check_type="text", payload={"text_value": "x" * 100}) == []
    errors = validate_item_payload(check_type="text", payload={"text_value": "x" * 20001})
    assert errors and "过长" in errors[0]


def test_errors_are_human_readable_chinese():
    """错误信息面向使用者，必须是中文且可操作 —— 不能只抛 422 状态码。"""
    errors = validate_item_payload(
        check_type="radio",
        payload={"text_value": "符合", "numeric_value": "abc"},
    )
    assert len(errors) >= 2, "多个问题应一次性全部返回，避免用户反复试错"
    for message in errors:
        assert any("\u4e00" <= ch <= "\u9fff" for ch in message), f"错误信息非中文：{message}"


# ---------------------------------------------------------------------------
# 4. 真实客户端载荷回归 —— 不得误伤正常保存
# ---------------------------------------------------------------------------
# 这一组用例直接照抄 h5-app / web-admin 的实际提交形态。
# 校验规则若写得过严，会把这些正常路径全部拒掉 ——
# 那等于我们亲手制造了「数据无法录入」，比原缺陷更糟。


def test_h5_full_payload_is_accepted():
    """H5 保存时**一次性提交全部结果字段**（其余为空串），必须放行。

    源码依据：``h5-app/src/views/InspectItem.vue`` 的 ``saveItem()``::

        const saveData = {
          template_item_id, radio_value, text_value, numeric_value,
          score_value, multi_value: ... || [], ...
        }
        await request.post(`/records/${recordId}/items`, saveData)

    注意 ``multi_value`` 恒为 ``[]``，``_is_blank`` 必须把空列表视为"未提供"。
    """
    h5_payload = {
        "radio_value": "pass",
        "text_value": "",
        "numeric_value": "",
        "score_value": "",
        "multi_value": [],
    }
    assert validate_item_payload(check_type="radio", payload=h5_payload) == [], (
        "H5 的全字段载荷被误拒 —— 正常保存会失败"
    )

    # text 类型的 H5 载荷：单选字段为空，文本字段有值
    assert (
        validate_item_payload(
            check_type="text",
            payload={**h5_payload, "radio_value": "", "text_value": "现场无异常"},
        )
        == []
    )


def test_web_admin_single_field_payload_is_accepted():
    """web-admin 逐字段提交 ``{template_item_id, [field]: value}``，必须放行。

    源码依据：``web-admin/src/components/InspectionForm/index.tsx``::

        await recordApi.createRecordItem(recordId, {
          template_item_id: ...,
          [field]: valueToSend,
        })

    该调用**不携带 check_type**，后端需回落到模板的 check_type。
    """
    assert validate_item_payload(check_type="radio", payload={"radio_value": "fail"}) == []
    assert validate_item_payload(check_type="numeric", payload={"numeric_value": "42"}) == []


def test_extra_fields_alongside_expected_field_are_tolerated():
    """该写的字段有值时，附带写了别的字段**不拒绝** —— 值不会丢，只是冗余。

    只有「该写的字段为空、值写到了别处」才真正造成数据丢失。
    """
    assert (
        validate_item_payload(
            check_type="radio",
            payload={"radio_value": "pass", "text_value": "现场备注"},
        )
        == []
    )


def test_pass_fail_alias_is_accepted():
    """``pass_fail`` 是旧字段 ``result_type`` 的取值，语义等同单选。

    前端读取时写的是 ``check_type || result_type || 'pass_fail'``，
    因此完全可能把 ``pass_fail`` 回传上来。若不认它，
    正常保存会被判成"未知类型"而拒绝。
    """
    assert validate_item_payload(check_type="pass_fail", payload={"radio_value": "pass"}) == []
    # 别名归一后，字段规则按 radio 执行
    errors = validate_item_payload(check_type="pass_fail", payload={"text_value": "x"})
    assert errors and "radio_value" in errors[0]


def test_alias_does_not_widen_accepted_types():
    """别名只是归一，不能把未知类型也放进来。"""
    assert validate_item_payload(check_type="rating", payload={"radio_value": "pass"})


# ---------------------------------------------------------------------------
# 4. 调用方必须传「真实类型」而非列默认值（静态门禁，不需数据库）
# ---------------------------------------------------------------------------


def test_records_guard_call_site_uses_resolve_check_type():
    """``POST /records/{id}/items`` 的守卫必须用 ``resolve_check_type()``。

    回归缺陷（2026-09-19 实测报出）：守卫直接读 ``template_item.check_type``，
    而 ``template_items.check_type`` **恒为列默认值 'radio'**
    （模板编辑器只写 ``result_type``）。生产库实测 174 个叶子检查项，
    ``check_type`` 全部是 'radio'，其中 8 个 ``result_type='numeric'``、
    3 个 ``result_type='text'`` —— 这 11 项在 Web 记录页提交时
    一律被判成"写错字段"而 422，**完全无法保存**。

    同一文件的快照写入用的是 ``resolve_check_type()``，两处口径必须一致。
    """
    import re
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1] / "app" / "routers" / "records.py"
    ).read_text(encoding="utf-8")

    # 定位守卫调用，检查它传给 check_type 的表达式
    call = re.search(r"guard_errors\s*=\s*validate_item_payload\((.*?)\n\s*\)", src, re.S)
    assert call, "未找到 validate_item_payload 调用点，records.py 结构可能已变更"

    # ⚠️ 必须先剥掉注释：说明性注释里会写到 `template_item.check_type` 这个字样，
    #    直接扫描会把注释当成实现（本门禁开发时真被绊过一次）。
    block = "\n".join(
        line.split("#", 1)[0] for line in call.group(1).splitlines()
    )

    assert "resolve_check_type(" in block, (
        "写入守卫必须用 resolve_check_type(template_item) 解析真实类型；"
        "直接读 template_item.check_type 会把数值型/描述型项误判为单选，"
        "导致前端正常提交被 422 拒绝"
    )
    assert "template_item.check_type" not in block, (
        "守卫又退回读原始 template_item.check_type（列默认 'radio'），"
        "会让数值型/描述型检查项无法保存"
    )


def test_records_has_no_raw_template_item_check_type_fallback():
    """records.py 内不得再出现「读 t_item.check_type 作类型」的写法。

    该列是列默认值，不能当类型用；类型一律走 resolve_check_type()。
    同样先剥注释再扫。
    """
    import re
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1] / "app" / "routers" / "records.py"
    ).read_text(encoding="utf-8")

    offenders = []
    for i, raw in enumerate(src.splitlines(), 1):
        code = raw.split("#", 1)[0]  # 剥掉行内注释
        if re.search(r"\bt_item\.check_type\b|\btemplate_item\.check_type\b", code):
            offenders.append(f"records.py:{i}: {raw.strip()}")
    assert not offenders, (
        "以下位置仍把列默认值 check_type 当类型使用，应改用 resolve_check_type()：\n  "
        + "\n  ".join(offenders)
    )
