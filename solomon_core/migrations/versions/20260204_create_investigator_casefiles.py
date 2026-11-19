# solomon_core/migrations/versions/20260204_create_investigator_casefiles.py
# ------------------------------------------------------------------
# Alembic Migration: Create Investigator CaseFiles Table
#
# Location:
#   solomon_core/migrations/versions/20260204_create_investigator_casefiles.py
#
# Purpose:
#   Introduces the append-only persistence table for Investigator
#   CaseFiles per Phase 69. Stores the full MVI CaseFile as an opaque
#   JSON artifact with immutable semantics.
#
# Governing Rules:
#   - One CaseFile per row
#   - case_id is the authoritative primary key
#   - No UPDATE or DELETE paths
#   - JSON payload is schema-agnostic
# ------------------------------------------------------------------

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision = "20260204_create_investigator_casefiles"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "investigator_casefiles",
        sa.Column("case_id", sa.String(length=64), primary_key=True),
        sa.Column("prior_case_id", sa.String(length=64), nullable=True),
        sa.Column("archetype_id", sa.String(length=64), nullable=False),
        sa.Column("casefile_version", sa.String(length=16), nullable=False),
        sa.Column("timestamp_emitted", sa.String(length=64), nullable=False),
        sa.Column("casefile_json", sa.JSON(), nullable=False),
    )


def downgrade():
    # Phase 69 policy: destructive downgrades are allowed only for migrations
    # not yet deployed to production.
    op.drop_table("investigator_casefiles")
