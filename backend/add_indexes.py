"""直接执行SQL添加性能优化索引"""
import asyncio
from sqlalchemy import text
from app.database import engine


async def add_indexes():
    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_template_items_template_id ON template_items (template_id)",
        "CREATE INDEX IF NOT EXISTS ix_template_items_parent_id ON template_items (parent_id)",
        "CREATE INDEX IF NOT EXISTS ix_template_items_sort_order ON template_items (sort_order)",
        
        "CREATE INDEX IF NOT EXISTS ix_inspection_tasks_status ON inspection_tasks (status)",
        "CREATE INDEX IF NOT EXISTS ix_inspection_tasks_assigned_to ON inspection_tasks (assigned_to)",
        "CREATE INDEX IF NOT EXISTS ix_inspection_tasks_template_id ON inspection_tasks (template_id)",
        "CREATE INDEX IF NOT EXISTS ix_inspection_tasks_created_at ON inspection_tasks (created_at)",
        
        "CREATE INDEX IF NOT EXISTS ix_task_item_records_task_id ON task_item_records (task_id)",
        "CREATE INDEX IF NOT EXISTS ix_task_item_records_template_item_id ON task_item_records (template_item_id)",
        "CREATE INDEX IF NOT EXISTS ix_task_item_records_result ON task_item_records (result)",
        
        "CREATE INDEX IF NOT EXISTS ix_audit_projects_enterprise_id ON audit_projects (enterprise_id)",
        "CREATE INDEX IF NOT EXISTS ix_audit_projects_status ON audit_projects (status)",
        "CREATE INDEX IF NOT EXISTS ix_audit_projects_created_at ON audit_projects (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_audit_projects_team_leader_id ON audit_projects (team_leader_id)",
        
        "CREATE INDEX IF NOT EXISTS ix_audit_plan_items_project_id ON audit_plan_items (project_id)",
        "CREATE INDEX IF NOT EXISTS ix_audit_plan_items_status ON audit_plan_items (status)",
        "CREATE INDEX IF NOT EXISTS ix_audit_plan_items_plan_date ON audit_plan_items (plan_date)",
        "CREATE INDEX IF NOT EXISTS ix_audit_plan_items_inspection_task_id ON audit_plan_items (inspection_task_id)",
        
        "CREATE INDEX IF NOT EXISTS ix_audit_team_members_project_id ON audit_team_members (project_id)",
        "CREATE INDEX IF NOT EXISTS ix_audit_team_members_member_id ON audit_team_members (member_id)",
        
        "CREATE INDEX IF NOT EXISTS ix_enterprises_name ON enterprises (name)",
        "CREATE INDEX IF NOT EXISTS ix_enterprises_created_at ON enterprises (created_at)",
        
        "CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)",
        
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs (action)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at)",
        
        "CREATE INDEX IF NOT EXISTS ix_inspection_tasks_status_created ON inspection_tasks (status, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_audit_projects_status_created ON audit_projects (status, created_at)",
    ]
    
    async with engine.begin() as conn:
        for sql in indexes:
            try:
                await conn.execute(text(sql))
                print(f"✓ {sql.split('INDEX IF NOT EXISTS ')[1].split(' ON')[0]}")
            except Exception as e:
                print(f"✗ {sql}: {e}")
    
    print("\n索引创建完成！")


if __name__ == "__main__":
    asyncio.run(add_indexes())
