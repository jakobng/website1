"""Add data_update_proposals table for community contributions.

Revision ID: 20260327_04
Revises: 20260326_03
Create Date: 2026-03-27 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260327_04'
down_revision = '20260326_03'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'data_update_proposals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('incentive_id', sa.Integer(), nullable=False),
        sa.Column('field_name', sa.String(), nullable=False),
        sa.Column('old_value', sa.String(), nullable=True),
        sa.Column('new_value', sa.String(), nullable=False),
        sa.Column('proposed_source_url', sa.Text(), nullable=False),
        sa.Column('proposed_source_description', sa.String(), nullable=True),
        sa.Column('proposer_email', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.Column('reviewed_at', sa.String(), nullable=True),
        sa.Column('reviewed_by', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_data_update_proposals_incentive_id'), 'data_update_proposals', ['incentive_id'], unique=False)
    op.create_index(op.f('ix_data_update_proposals_status'), 'data_update_proposals', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_data_update_proposals_status'), table_name='data_update_proposals')
    op.drop_index(op.f('ix_data_update_proposals_incentive_id'), table_name='data_update_proposals')
    op.drop_table('data_update_proposals')
