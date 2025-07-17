"""add lead outreach product."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c31e089201f0"  # Unique ID for this migration
down_revision = "161918133bec"  # The latest 'schema' head from the core library
branch_labels = ("data",)
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO products (product_id, name, description, product_type, tag, status)
            VALUES ('8745b530-5780-4960-b33c-3c3b028562d9', 'LeadOutreach', 'A lead outreach campaign.', 'LeadOutreachCampaign', 'LEADOUTREACH', 'active');
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM products WHERE product_id = '8745b530-5780-4960-b33c-3c3b028562d9'"
        )
    )
