"""根节点 / 分类目录规则的单元测试。

覆盖《第 4 步：根节点与层级关系重构》的核心业务规则：

1. **父节点身份唯一性**：只要节点下存在有效子节点，就必须判为分类目录
   （即使 ``is_category`` 字段是脏的）。
2. **禁止检查项内容下沉到父节点**：分类目录必须清空全部检查项属性。
3. **任务派发严格叶子化**：创建任务时不得为分类目录生成空填报记录。

这些用例对应外部测试暴露的 P0-01 / P0-02 / P0-03，属于回归防线。
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.utils.category import (
    CATEGORY_FIELD_OVERRIDES,
    clear_check_item_fields,
    is_category_node,
    load_parent_ids,
    normalize_as_category,
)


# ---------------------------------------------------------------------------
# 1. 分类目录判定
# ---------------------------------------------------------------------------


class TestIsCategoryNode:
    """is_category_node：只要挂了子节点就必须判为分类目录。"""

    def test_none_is_not_category(self):
        assert is_category_node(None) is False

    def test_explicit_flag_true(self):
        item = SimpleNamespace(id=uuid4(), is_category=True)
        assert is_category_node(item) is True

    def test_dirty_data_with_children_is_upgraded(self):
        """脏数据兜底：is_category=False 但有子节点 → 仍判为分类目录。

        这正是外部测试里"根节点被当成检查项、显示未填写"的根因场景。
        """
        parent_id = uuid4()
        dirty_parent = SimpleNamespace(id=parent_id, is_category=False)
        assert is_category_node(dirty_parent, {parent_id}) is True

    def test_dirty_data_with_flag_none_is_upgraded(self):
        parent_id = uuid4()
        dirty_parent = SimpleNamespace(id=parent_id, is_category=None)
        assert is_category_node(dirty_parent, {parent_id}) is True

    def test_real_leaf_stays_check_item(self):
        leaf = SimpleNamespace(id=uuid4(), is_category=False)
        assert is_category_node(leaf, {uuid4()}) is False

    def test_leaf_with_empty_parent_ids(self):
        leaf = SimpleNamespace(id=uuid4(), is_category=False)
        assert is_category_node(leaf, set()) is False
        assert is_category_node(leaf) is False


# ---------------------------------------------------------------------------
# 2. 分类目录字段清单（防止清单漂移）
# ---------------------------------------------------------------------------


class TestCategoryFieldOverrides:
    """字段清单必须完整，历史上就漏过 is_required。"""

    CONTENT_FIELDS = (
        "result_type",
        "result_options",
        "min_value",
        "max_value",
        "unit",
        "score_weight",
        "default_score",
        "check_method",
        "legal_basis",
        "standard_ref",
        "ai_prompt_template",
        "risk_level",
    )
    FLAG_FIELDS = ("use_ai", "attachment_required", "allow_attachment", "is_required")

    def test_all_content_fields_are_cleared(self):
        for field in self.CONTENT_FIELDS:
            assert field in CATEGORY_FIELD_OVERRIDES, f"字段清单缺少 {field}"
            assert CATEGORY_FIELD_OVERRIDES[field] is None, f"{field} 应被清空"

    def test_all_flag_fields_are_disabled(self):
        for field in self.FLAG_FIELDS:
            assert field in CATEGORY_FIELD_OVERRIDES, f"字段清单缺少 {field}"
            assert CATEGORY_FIELD_OVERRIDES[field] is False, f"{field} 应置为 False"

    def test_is_category_is_true(self):
        assert CATEGORY_FIELD_OVERRIDES["is_category"] is True

    def test_is_required_is_explicitly_covered(self):
        """回归：create_item 曾漏设 is_required，导致三处清单不一致。"""
        assert "is_required" in CATEGORY_FIELD_OVERRIDES


class TestNormalizeAsCategory:
    """normalize_as_category：就地把 ORM 条目规范为纯分类目录。"""

    def test_clears_all_check_item_content(self):
        item = SimpleNamespace(
            id=uuid4(),
            is_category=False,
            result_type="pass_fail",
            result_options=[{"value": "pass"}],
            min_value=1,
            max_value=10,
            unit="分",
            score_weight=5,
            default_score=3,
            check_method="现场查看",
            legal_basis="某法第 3 条",
            standard_ref="GB/T 1234",
            ai_prompt_template="请判断",
            risk_level="high",
            use_ai=True,
            attachment_required=True,
            allow_attachment=True,
            is_required=True,
        )

        normalize_as_category(item)

        assert item.is_category is True
        assert item.result_type is None
        assert item.result_options is None
        assert item.min_value is None
        assert item.max_value is None
        assert item.unit is None
        assert item.score_weight is None
        assert item.default_score is None
        assert item.check_method is None
        assert item.legal_basis is None
        assert item.standard_ref is None
        assert item.ai_prompt_template is None
        assert item.risk_level is None
        assert item.use_ai is False
        assert item.attachment_required is False
        assert item.allow_attachment is False
        assert item.is_required is False

    def test_tolerates_missing_attributes(self):
        """字段不全的对象也不应抛 AttributeError。"""
        item = SimpleNamespace(is_category=False)
        normalize_as_category(item)
        assert item.is_category is True

    def test_does_not_touch_title_or_description(self):
        item = SimpleNamespace(
            id=uuid4(),
            title="1、生产环境条件",
            description="大类说明",
            is_category=False,
        )
        normalize_as_category(item)
        assert item.title == "1、生产环境条件"
        assert item.description == "大类说明"


class TestClearCheckItemFields:
    """字典形式的快照清洗。"""

    def test_only_touches_existing_keys(self):
        payload = {
            "title": "测试级别",
            "is_category": False,
            "result_type": "pass_fail",
        }
        clear_check_item_fields(payload)

        assert payload["title"] == "测试级别"
        assert payload["is_category"] is True
        assert payload["result_type"] is None
        # 未出现的键不应被凭空塞进去
        assert "score_weight" not in payload


# ---------------------------------------------------------------------------
# 3. 父节点集合查询
# ---------------------------------------------------------------------------


class TestLoadParentIds:
    """load_parent_ids：SQL 层收集"有有效子节点"的父节点。"""

    def test_collects_dedupes_and_drops_nulls(self):
        p1, p2 = uuid4(), uuid4()
        db = AsyncMock()
        rows = Mock()
        rows.all.return_value = [(p1,), (p2,), (p1,), (None,)]
        db.execute = AsyncMock(return_value=rows)

        ids = asyncio.run(load_parent_ids(db, template_id=uuid4()))

        assert ids == {p1, p2}
        assert db.execute.await_count == 1

    def test_returns_empty_set_when_no_parents(self):
        db = AsyncMock()
        rows = Mock()
        rows.all.return_value = []
        db.execute = AsyncMock(return_value=rows)

        assert asyncio.run(load_parent_ids(db)) == set()


# ---------------------------------------------------------------------------
# 4. update_item：有子节点时强制锁定为分类目录
# ---------------------------------------------------------------------------


def _make_update_item_env(children_count: int):
    """构造 update_item 所需的 mock 环境。"""
    from app.routers import templates as templates_module

    template_id = uuid4()
    item = SimpleNamespace(
        id=uuid4(),
        template_id=template_id,
        parent_id=None,
        title="测试难度",
        is_category=False,
        description=None,
        result_type="pass_fail",
        check_type="radio",
        risk_level="medium",
        sort_order=0,
        result_options=None,
        min_value=None,
        max_value=None,
        unit=None,
        score_weight=10,
        default_score=5,
        check_method="现场查看",
        legal_basis=None,
        standard_ref=None,
        ai_prompt_template=None,
        use_ai=True,
        allow_attachment=True,
        attachment_required=True,
        is_required=True,
    )
    template = SimpleNamespace(id=template_id, created_by=uuid4(), is_public=False)
    admin = SimpleNamespace(id=uuid4(), username="admin", role="admin")

    count_row = Mock()
    count_row.scalar.return_value = children_count

    db = AsyncMock()

    async def fake_get(model, key):
        from app.models.template import InspectionTemplate, TemplateItem

        if model is TemplateItem:
            return item
        if model is InspectionTemplate:
            return template
        return None

    db.get = AsyncMock(side_effect=fake_get)
    db.execute = AsyncMock(return_value=count_row)
    return templates_module, db, admin, item


class TestUpdateItemCategoryLock:
    """update_item：只要存在有效子项，前端传什么都必须锁死为分类目录。"""

    def test_has_children_forces_category_and_clears_fields(self):
        from app.schemas import TemplateItemUpdate

        templates_module, db, admin, item = _make_update_item_env(children_count=2)
        payload = TemplateItemUpdate(
            title="测试难度",
            is_category=False,          # 前端仍传 False，必须被忽略
            result_type="pass_fail",
            is_required=True,
            score_weight=10,
            use_ai=True,
        )

        asyncio.run(templates_module.update_item(str(item.id), payload, db, admin))

        assert item.is_category is True
        assert item.is_required is False
        assert item.result_type is None
        assert item.score_weight is None
        assert item.use_ai is False
        assert item.check_method is None
        assert item.title == "测试难度"

    def test_leaf_can_stay_check_item(self):
        from app.schemas import TemplateItemUpdate

        templates_module, db, admin, item = _make_update_item_env(children_count=0)
        payload = TemplateItemUpdate(title="难度特高", is_category=False)

        asyncio.run(templates_module.update_item(str(item.id), payload, db, admin))

        # 没有子节点时不应被强制升级
        assert item.is_category is False

    def test_explicit_category_flag_clears_fields_without_children(self):
        from app.schemas import TemplateItemUpdate

        templates_module, db, admin, item = _make_update_item_env(children_count=0)
        payload = TemplateItemUpdate(title="空分类", is_category=True, score_weight=10)

        asyncio.run(templates_module.update_item(str(item.id), payload, db, admin))

        assert item.is_category is True
        assert item.score_weight is None
        assert item.is_required is False


# ---------------------------------------------------------------------------
# 5. 任务派发严格叶子化
# ---------------------------------------------------------------------------


class TestCreateRecordsFromTemplate:
    """_create_records_from_template：分类目录不得生成空填报记录。"""

    def test_only_leaf_items_get_records(self):
        from app.models.task import TaskItemRecord
        from app.services.services import TaskService

        template_id = uuid4()
        category_id, leaf_id = uuid4(), uuid4()

        category_item = SimpleNamespace(
            id=category_id, template_id=template_id, is_category=True
        )
        # 脏数据：有子节点但 is_category 未标记，同样不能派发
        dirty_parent = SimpleNamespace(
            id=uuid4(), template_id=template_id, is_category=False
        )
        leaf_item = SimpleNamespace(
            id=leaf_id, template_id=template_id, is_category=False
        )

        parents_result = Mock()
        parents_result.all.return_value = [(category_id,), (dirty_parent.id,)]
        items_result = Mock()
        items_result.scalars.return_value.all.return_value = [
            category_item,
            dirty_parent,
            leaf_item,
        ]

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[parents_result, items_result])

        task = SimpleNamespace(id=uuid4(), template_id=template_id)
        asyncio.run(TaskService._create_records_from_template(db, task))

        added = [call.args[0] for call in db.add.call_args_list]
        assert len(added) == 1, f"应只为叶子检查项派发记录，实际派发 {len(added)} 条"
        assert isinstance(added[0], TaskItemRecord)
        assert added[0].template_item_id == leaf_id
        db.commit.assert_awaited()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
