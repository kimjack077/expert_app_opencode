"""创建检查记录表

Revision ID: create_inspection_records
Revises: 
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'create_inspection_records'
down_revision = 'refactor_template'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 删除旧的 inspection_records 表（如果存在）
    op.execute('DROP TABLE IF EXISTS inspection_records CASCADE')
    op.execute('DROP TABLE IF EXISTS inspection_record_items CASCADE')
    
    # 创建 inspection_records 表（如果不存在）
    op.execute('''
        CREATE TABLE IF NOT EXISTS inspection_records (
            id UUID NOT NULL,
            template_id UUID NOT NULL,
            enterprise_id UUID,
            enterprise_name VARCHAR(200),
            enterprise_address VARCHAR(500),
            contact_person VARCHAR(100),
            contact_phone VARCHAR(20),
            inspector_id UUID NOT NULL,
            inspection_date TIMESTAMP WITH TIME ZONE DEFAULT now(),
            status VARCHAR(20),
            overall_result VARCHAR(20),
            remarks TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            PRIMARY KEY (id),
            FOREIGN KEY(template_id) REFERENCES inspection_templates (id),
            FOREIGN KEY(enterprise_id) REFERENCES enterprises (id),
            FOREIGN KEY(inspector_id) REFERENCES users (id)
        )
    ''')

    # 创建 inspection_record_items 表（如果不存在）
    op.execute('''
        CREATE TABLE IF NOT EXISTS inspection_record_items (
            id UUID NOT NULL,
            record_id UUID NOT NULL,
            template_item_id UUID,
            result VARCHAR(20),
            result_value VARCHAR(50),
            result_text TEXT,
            inspector_note TEXT,
            photos JSONB,
            recorded_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            PRIMARY KEY (id),
            FOREIGN KEY(record_id) REFERENCES inspection_records (id) ON DELETE CASCADE,
            FOREIGN KEY(template_item_id) REFERENCES template_items (id)
        )
    ''')

    # 创建索引（如果不存在）
    op.execute('CREATE INDEX IF NOT EXISTS idx_records_template ON inspection_records (template_id)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_records_enterprise ON inspection_records (enterprise_id)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_records_inspector ON inspection_records (inspector_id)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_records_date ON inspection_records (inspection_date)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_record_items_record ON inspection_record_items (record_id)')


def downgrade() -> None:
    # 删除索引
    op.drop_index('idx_record_items_record', table_name='inspection_record_items')
    op.drop_index('idx_records_date', table_name='inspection_records')
    op.drop_index('idx_records_inspector', table_name='inspection_records')
    op.drop_index('idx_records_enterprise', table_name='inspection_records')
    op.drop_index('idx_records_template', table_name='inspection_records')

    # 删除表
    op.drop_table('inspection_record_items')
    op.drop_table('inspection_records')
