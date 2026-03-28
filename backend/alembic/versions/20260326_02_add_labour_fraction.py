"""Add labour_fraction column to Incentive model.

Revision ID: 20260326_02
Revises: 20260326_01
Create Date: 2026-03-26

The labour_fraction field allows per-incentive specification of what fraction
of qualifying spend counts as labour for labour_only rebates (e.g., Canada CPTC).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260326_02"
down_revision = "20260326_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('incentives', sa.Column('labour_fraction', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('incentives', 'labour_fraction')
