"""Add enterprise and knowledge models

Revision ID: add_enterprise_knowledge
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_enterprise_knowledge'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'enterprises',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('credit_code', sa.String(50), nullable=True),
        sa.Column('org_code', sa.String(50), nullable=True),
        sa.Column('address', sa.String(500), nullable=True),
        sa.Column('legal_person', sa.String(50), nullable=True),
        sa.Column('contact_person', sa.String(50), nullable=True),
        sa.Column('contact_phone', sa.String(20), nullable=True),
        sa.Column('enterprise_type', sa.String(50), nullable=True),
        sa.Column('economic_type', sa.String(50), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=True, default='B'),
        sa.Column('status', sa.String(20), nullable=True, default='active'),
        sa.Column('longitude', sa.Numeric(10, 7), nullable=True),
        sa.Column('latitude', sa.Numeric(10, 7), nullable=True),
        sa.Column('district', sa.String(50), nullable=True),
        sa.Column('street', sa.String(100), nullable=True),
        sa.Column('employee_count', sa.Integer, nullable=True),
        sa.Column('annual_output', sa.Numeric(15, 2), nullable=True),
        sa.Column('annual_tax', sa.Numeric(15, 2), nullable=True),
        sa.Column('remarks', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('credit_code'),
    )
    op.create_index('ix_enterprises_credit_code', 'enterprises', ['credit_code'])
    op.create_index('ix_enterprises_org_code', 'enterprises', ['org_code'])

    op.create_table(
        'enterprise_qualifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('enterprise_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('qual_type', sa.String(50), nullable=False),
        sa.Column('cert_no', sa.String(100), nullable=True),
        sa.Column('product_name', sa.String(200), nullable=True),
        sa.Column('issue_date', sa.Date, nullable=True),
        sa.Column('valid_from', sa.Date, nullable=True),
        sa.Column('valid_until', sa.Date, nullable=True),
        sa.Column('issue_authority', sa.String(200), nullable=True),
        sa.Column('status', sa.String(20), nullable=True, default='valid'),
        sa.Column('remarks', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['enterprise_id'], ['enterprises.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'enterprise_products',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('enterprise_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('specification', sa.String(200), nullable=True),
        sa.Column('output_unit', sa.String(20), nullable=True),
        sa.Column('annual_output', sa.Numeric(15, 2), nullable=True),
        sa.Column('cert_status', sa.String(20), nullable=True),
        sa.Column('remarks', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['enterprise_id'], ['enterprises.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'enterprise_equipment',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('enterprise_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('manufacturer', sa.String(200), nullable=True),
        sa.Column('purchase_date', sa.Date, nullable=True),
        sa.Column('status', sa.String(20), nullable=True, default='normal'),
        sa.Column('remarks', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['enterprise_id'], ['enterprises.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'enterprise_instruments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('enterprise_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('serial_no', sa.String(100), nullable=True),
        sa.Column('measure_range', sa.String(100), nullable=True),
        sa.Column('accuracy', sa.String(50), nullable=True),
        sa.Column('verification_method', sa.String(50), nullable=True),
        sa.Column('last_verified', sa.Date, nullable=True),
        sa.Column('next_verified', sa.Date, nullable=True),
        sa.Column('status', sa.String(20), nullable=True, default='normal'),
        sa.Column('remarks', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['enterprise_id'], ['enterprises.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'enterprise_personnel',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('enterprise_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('position', sa.String(50), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('id_card', sa.String(20), nullable=True),
        sa.Column('education', sa.String(50), nullable=True),
        sa.Column('certificate', sa.String(100), nullable=True),
        sa.Column('cert_valid_until', sa.Date, nullable=True),
        sa.Column('remarks', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['enterprise_id'], ['enterprises.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'rectification_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('enterprise_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('issue_description', sa.Text, nullable=False),
        sa.Column('rectification_requirement', sa.Text, nullable=True),
        sa.Column('deadline', sa.Date, nullable=True),
        sa.Column('status', sa.String(20), nullable=True, default='pending'),
        sa.Column('rectification_result', sa.Text, nullable=True),
        sa.Column('rectified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewer', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('transfer_to_inspection', sa.Boolean, nullable=True, default=False),
        sa.Column('transfer_no', sa.String(50), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['enterprise_id'], ['enterprises.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['inspection_tasks.id']),
        sa.ForeignKeyConstraint(['reviewer'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'knowledge_categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('code', sa.String(50), nullable=True),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('category_type', sa.String(50), nullable=True),
        sa.Column('sort_order', sa.Integer, nullable=True, default=0),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['parent_id'], ['knowledge_categories.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'knowledge_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('doc_type', sa.String(50), nullable=True),
        sa.Column('doc_no', sa.String(100), nullable=True),
        sa.Column('content', sa.Text, nullable=True),
        sa.Column('summary', sa.Text, nullable=True),
        sa.Column('keywords', sa.String(500), nullable=True),
        sa.Column('issue_authority', sa.String(200), nullable=True),
        sa.Column('issue_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expiry_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=True, default='effective'),
        sa.Column('file_url', sa.String(500), nullable=True),
        sa.Column('file_name', sa.String(200), nullable=True),
        sa.Column('view_count', sa.Integer, nullable=True, default=0),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['category_id'], ['knowledge_categories.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'inspection_guidelines',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('code', sa.String(50), nullable=True),
        sa.Column('product_category', sa.String(100), nullable=True),
        sa.Column('content', sa.Text, nullable=True),
        sa.Column('legal_basis', sa.Text, nullable=True),
        sa.Column('version', sa.String(20), nullable=True, default='1.0'),
        sa.Column('is_active', sa.Boolean, nullable=True, default=True),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('inspection_guidelines')
    op.drop_table('knowledge_documents')
    op.drop_table('knowledge_categories')
    op.drop_table('rectification_records')
    op.drop_table('enterprise_personnel')
    op.drop_table('enterprise_instruments')
    op.drop_table('enterprise_equipment')
    op.drop_table('enterprise_products')
    op.drop_table('enterprise_qualifications')
    op.drop_index('ix_enterprises_org_code')
    op.drop_index('ix_enterprises_credit_code')
    op.drop_table('enterprises')
