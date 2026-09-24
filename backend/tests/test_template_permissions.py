"""模板行级编辑权限回归测试。"""

from types import SimpleNamespace
from uuid import uuid4

from app.routers.templates import can_modify_template


def test_expert_can_only_edit_templates_they_created():
    expert = SimpleNamespace(id=uuid4(), role="expert")
    own_template = SimpleNamespace(created_by=expert.id)
    admin_template = SimpleNamespace(created_by=uuid4())

    assert can_modify_template(expert, own_template) is True
    assert can_modify_template(expert, admin_template) is False


def test_admin_can_edit_templates_created_by_other_users():
    admin = SimpleNamespace(id=uuid4(), role="admin")
    template = SimpleNamespace(created_by=uuid4())

    assert can_modify_template(admin, template) is True
