"""add_judgment_note_to_inspection_records

Revision ID: e7b23f8910cd
Revises: 2ef58ca8bdd1
Create Date: 2026-09-18 10:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e7b23f8910cd'
down_revision = '2ef58ca8bdd1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'inspection_records',
        sa.Column('judgment_note', sa.Text(), nullable=True, comment='判定说明')
    )


def downgrade():
    op.drop_column('inspection_records', 'judgment_note')
