"""Add source_alerts table for freshness monitoring.

Revision ID: 20260326_03
Revises: 20260326_02
Create Date: 2026-03-26 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260326_03'
down_revision = '20260326_02'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'source_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('incentive_id', sa.Integer(), nullable=False),
        sa.Column('last_verified', sa.String(), nullable=True),
        sa.Column('days_old', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('checked_at', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_source_alerts_incentive_id'), 'source_alerts', ['incentive_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_source_alerts_incentive_id'), table_name='source_alerts')
    op.drop_table('source_alerts')
