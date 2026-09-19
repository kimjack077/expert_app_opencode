"""检查项完成度判据的单元测试。

锁定两件事：

1. **类型解析**：``template_items`` 上 ``check_type`` 恒为列默认值 ``'radio'``，
   真实类型在 ``result_type``。只看 ``check_type`` 会把描述型/数值型检查项
   误判为判定型，导致「明明填了内容却显示未评定」。
2. **完成度口径**：合格/不合格/不适用都算完成；描述型/数值型/打分型填了内容
   也算完成；全空才算未评定。
"""

import pytest

from app.utils.item_completion import is_item_assessed, resolve_check_type

pytestmark = pytest.mark.unit


class Item:
    """模拟 template_items 行（两个类型字段并存）。"""

    def __init__(self, check_type=None, result_type=None):
        self.check_type = check_type
        self.result_type = result_type


class Record:
    """模拟记录行（task_item_records 与 inspection_record_items 的字段并集）。"""

    def __init__(self, **kwargs):
        for field in (
            "result",
            "result_value",
            "result_text",
            "radio_value",
            "text_value",
            "numeric_value",
            "score_value",
            "multi_value",
            "evaluation_3level",
        ):
            setattr(self, field, kwargs.get(field))


# --------------------------------------------------------------------------
# 类型解析
# --------------------------------------------------------------------------


def test_result_type_优先于默认的_check_type():
    """实测形态：check_type='radio'（默认）、result_type='text'（真实）。"""
    assert resolve_check_type(Item("radio", "text")) == "text"
    assert resolve_check_type(Item("radio", "numeric")) == "numeric"
    assert resolve_check_type(Item("radio", "pass_fail")) == "radio"


def test_check_type_非默认时优先使用():
    """AI 导入路径写的是 check_type，且可能是非默认值。"""
    assert resolve_check_type(Item("numeric", "pass_fail")) == "numeric"
    assert resolve_check_type(Item("text", "pass_fail")) == "text"
    assert resolve_check_type(Item("audit_3level", "pass_fail")) == "audit_3level"


def test_两者都非默认时以_check_type_为准():
    assert resolve_check_type(Item("score", "text")) == "score"


def test_字段缺失或为默认时回落到判定型():
    assert resolve_check_type(Item()) == "radio"
    assert resolve_check_type(Item("radio", "pass_fail")) == "radio"
    assert resolve_check_type(None) == "radio"


def test_多选别名归一为_multi_check():
    assert resolve_check_type(Item("multi_check", None)) == "multi_check"
    assert resolve_check_type(Item("multiselect", None)) == "multi_check"


# --------------------------------------------------------------------------
# 完成度口径
# --------------------------------------------------------------------------


def test_判定型三种结论都算完成():
    for verdict in ("pass", "fail", "na", "not_applicable"):
        assert is_item_assessed(Item("radio", "pass_fail"), Record(result=verdict))


def test_判定型只写备注不算完成():
    """备注不是结论，未评定就是未完成。"""
    assert not is_item_assessed(
        Item("radio", "pass_fail"), Record(inspector_note="现场看了看，还行")
    )


def test_描述型填了文本即算完成():
    assert is_item_assessed(Item("radio", "text"), Record(result_text="现场符合要求"))
    assert not is_item_assessed(Item("radio", "text"), Record())


def test_数值型填了数值即算完成():
    assert is_item_assessed(Item("radio", "numeric"), Record(result_value="98.5"))
    assert not is_item_assessed(Item("radio", "numeric"), Record())


def test_打分型填了分数即算完成():
    assert is_item_assessed(Item("score", "pass_fail"), Record(score_value=8))
    assert not is_item_assessed(Item("score", "pass_fail"), Record())


def test_多选型选了选项即算完成():
    assert is_item_assessed(Item("multi_check", None), Record(multi_value=["a"]))
    assert not is_item_assessed(Item("multi_check", None), Record(multi_value=[]))


def test_inspection_record_items_字段名同样适用():
    """Web 检查记录用 radio_value / text_value / numeric_value。"""
    assert is_item_assessed(Item("radio", "pass_fail"), Record(radio_value="pass"))
    assert is_item_assessed(Item("radio", "text"), Record(text_value="描述内容"))
    assert is_item_assessed(Item("radio", "numeric"), Record(numeric_value="12"))


def test_空串与字面量_null_视为未填写():
    assert not is_item_assessed(Item("radio", "text"), Record(result_text="   "))
    assert not is_item_assessed(Item("radio", "text"), Record(result_text="null"))
    assert not is_item_assessed(Item("radio", "numeric"), Record(result_value=""))


def test_缺省_record_时以_item_自身为准():
    assert is_item_assessed(Record(result="pass"))
    assert not is_item_assessed(Record())
