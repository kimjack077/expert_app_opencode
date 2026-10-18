"""add hot-path indexes for tasks / records / plan items / audit logs

Revision ID: a7c1e9f4b2d0
Revises: 35f52a3d6ee3
Create Date: 2026-10-18 10:00:00.000000

线上性能排查（2026-10-18）发现的热路径缺索引。此前只有主键与
``is_deleted`` 单列索引，所有按任务/记录/计划项/用户过滤的查询都在做
全表扫描；数据量小时看不出来，一旦记录表增长就是全站变慢。

新增索引（全部 IF NOT EXISTS，可重复执行）：
1. ``task_item_records(task_id)``
   —— 任务检查项加载、完成校验、AI 最终判定、统计重算，每次任务操作都查。
2. ``task_item_records(template_item_id)``
   —— 记录与模板项关联回查。
3. ``inspection_record_items(record_id)`` / ``(audit_area_record_id)``
   —— 检查记录详情、报告生成、区域记录编辑。
4. ``audit_plan_items(inspection_task_id)``
   —— 任务 ↔ 计划项双向查询（列表接口按一批 task_id 批量回填）。
5. ``audit_plan_items(project_id)`` / ``audit_area_records(project_id)`` /
   ``nonconformities(project_id)``
   —— 审核项目详情页的四个子列表。
6. ``media_files(record_id)`` / ``media_files(task_id)``
   —— 检查记录附件回显、任务照片列表。
7. ``audit_logs(created_at)`` / ``audit_logs(user_id)``
   —— 审计日志页按时间倒序分页。
8. ``users(role)``、``inspection_tasks(assigned_to, status)``
   —— 专家"我的任务"过滤。
9. ``template_items(template_id, sort_order)``
    —— 模板项按排序加载（树构建与任务派发）。

注：
* ``inspection_records`` 表没有 task_id 列（任务同步记录通过 remarks 中的
  ``[task:<uuid>]`` 标记反查），因此这里不为其建 task_id 索引。
* ``inspection_record_items`` 存在历史重复数据，不建唯一索引。
"""
from alembic import op


revision = 'a7c1e9f4b2d0'
down_revision = '35f52a3d6ee3'
branch_labels = None
depends_on = None


_INDEXES = (
    ("idx_task_item_records_task", "task_item_records", "task_id"),
    ("idx_task_item_records_template_item", "task_item_records", "template_item_id"),
    ("idx_record_items_record", "inspection_record_items", "record_id"),
    ("idx_record_items_area_record", "inspection_record_items", "audit_area_record_id"),
    ("idx_plan_items_inspection_task", "audit_plan_items", "inspection_task_id"),
    ("idx_plan_items_project", "audit_plan_items", "project_id"),
    ("idx_area_records_project", "audit_area_records", "project_id"),
    ("idx_nonconformities_project", "nonconformities", "project_id"),
    ("idx_media_files_record", "media_files", "record_id"),
    ("idx_media_files_task", "media_files", "task_id"),
    ("idx_audit_logs_created_at", "audit_logs", "created_at"),
    ("idx_audit_logs_user", "audit_logs", "user_id"),
    ("idx_users_role", "users", "role"),
)

_COMPOSITE_INDEXES = (
    (
        "idx_inspection_tasks_assignee_status",
        "inspection_tasks",
        "assigned_to, status",
    ),
    (
        "idx_template_items_template_sort",
        "template_items",
        "template_id, sort_order",
    ),
)


def upgrade():
    for name, table, column in _INDEXES:
        op.execute(
            f'CREATE INDEX IF NOT EXISTS {name} ON {table} ({column})'
        )
    for name, table, columns in _COMPOSITE_INDEXES:
        op.execute(
            f'CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})'
        )


def downgrade():
    for name, _table, _column in _INDEXES:
        op.execute(f'DROP INDEX IF EXISTS {name}')
    for name, _table, _columns in _COMPOSITE_INDEXES:
        op.execute(f'DROP INDEX IF EXISTS {name}')
