"""Baseline schema for CoPro Calculator.

Revision ID: 20260326_01
Revises:
Create Date: 2026-03-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260326_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incentives",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("region", sa.String(), nullable=True),
        sa.Column("incentive_type", sa.String(), nullable=False),
        sa.Column("rebate_percent", sa.Float(), nullable=True),
        sa.Column("rebate_applies_to", sa.String(), nullable=True),
        sa.Column("max_cap_amount", sa.Float(), nullable=True),
        sa.Column("max_cap_currency", sa.String(length=3), nullable=True),
        sa.Column("min_total_budget", sa.Float(), nullable=True),
        sa.Column("min_qualifying_spend", sa.Float(), nullable=True),
        sa.Column("min_spend_currency", sa.String(length=3), nullable=True),
        sa.Column("min_spend_percent", sa.Float(), nullable=True),
        sa.Column("min_shoot_percent", sa.Float(), nullable=True),
        sa.Column("min_shoot_days", sa.Integer(), nullable=True),
        sa.Column("min_total_budget_documentary", sa.Float(), nullable=True),
        sa.Column("min_qualifying_spend_documentary", sa.Float(), nullable=True),
        sa.Column("eligible_formats", sa.JSON(), nullable=True),
        sa.Column("eligible_stages", sa.JSON(), nullable=True),
        sa.Column("mutually_exclusive_with", sa.JSON(), nullable=True),
        sa.Column("local_producer_required", sa.Boolean(), nullable=True),
        sa.Column("local_crew_min_percent", sa.Float(), nullable=True),
        sa.Column("post_production_local_required", sa.Boolean(), nullable=True),
        sa.Column("post_spend_min_percent", sa.Float(), nullable=True),
        sa.Column("cultural_test_required", sa.Boolean(), nullable=True),
        sa.Column("cultural_test_min_score", sa.Integer(), nullable=True),
        sa.Column("cultural_test_total_score", sa.Integer(), nullable=True),
        sa.Column("conditional_rates", sa.JSON(), nullable=True),
        sa.Column("stacking_allowed", sa.Boolean(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_description", sa.String(), nullable=True),
        sa.Column("clause_reference", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_verified", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incentives_country_code", "incentives", ["country_code"], unique=False)
    op.create_index("ix_incentives_id", "incentives", ["id"], unique=False)

    op.create_table(
        "treaties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("treaty_type", sa.String(), nullable=True),
        sa.Column("country_a_code", sa.String(length=2), nullable=False),
        sa.Column("country_b_code", sa.String(length=2), nullable=True),
        sa.Column("min_share_percent", sa.Float(), nullable=True),
        sa.Column("max_share_percent", sa.Float(), nullable=True),
        sa.Column("min_share_third_party", sa.Float(), nullable=True),
        sa.Column("eligible_formats", sa.JSON(), nullable=True),
        sa.Column("creative_contribution_required", sa.Boolean(), nullable=True),
        sa.Column("creative_requirements_summary", sa.Text(), nullable=True),
        sa.Column("competent_authority_a", sa.String(), nullable=True),
        sa.Column("competent_authority_b", sa.String(), nullable=True),
        sa.Column("requires_prior_approval", sa.Boolean(), nullable=True),
        sa.Column("date_signed", sa.String(), nullable=True),
        sa.Column("date_entered_force", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_description", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_verified", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_treaties_id", "treaties", ["id"], unique=False)

    op.create_table(
        "multilateral_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("treaty_id", sa.Integer(), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("date_ratified", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_multilateral_members_id", "multilateral_members", ["id"], unique=False)

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("document_type", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("country_codes", sa.JSON(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("original_url", sa.Text(), nullable=True),
        sa.Column("publisher", sa.String(), nullable=True),
        sa.Column("date_downloaded", sa.String(), nullable=True),
        sa.Column("incentive_id", sa.Integer(), nullable=True),
        sa.Column("treaty_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("filename"),
    )
    op.create_index("ix_documents_id", "documents", ["id"], unique=False)

    op.create_table(
        "document_annotations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=True),
        sa.Column("clause_reference", sa.String(), nullable=True),
        sa.Column("topic", sa.String(), nullable=True),
        sa.Column("original_text", sa.Text(), nullable=True),
        sa.Column("english_summary", sa.Text(), nullable=False),
        sa.Column("incentive_id", sa.Integer(), nullable=True),
        sa.Column("treaty_id", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_annotations_id", "document_annotations", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_document_annotations_id", table_name="document_annotations")
    op.drop_table("document_annotations")

    op.drop_index("ix_documents_id", table_name="documents")
    op.drop_table("documents")

    op.drop_index("ix_multilateral_members_id", table_name="multilateral_members")
    op.drop_table("multilateral_members")

    op.drop_index("ix_treaties_id", table_name="treaties")
    op.drop_table("treaties")

    op.drop_index("ix_incentives_id", table_name="incentives")
    op.drop_index("ix_incentives_country_code", table_name="incentives")
    op.drop_table("incentives")
