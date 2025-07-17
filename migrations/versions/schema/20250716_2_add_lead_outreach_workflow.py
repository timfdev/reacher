"""add lead outreach workflow."""

from alembic import op
from orchestrator.migrations.helpers import create_workflow, delete_workflow

# revision identifiers, used by Alembic.
revision = "a4f8e08523c4"  # A new, unique ID
down_revision = "c31e089201f0"  # This migration depends on the one above
branch_labels = None
depends_on = None

new_workflows = [
    {
        "name": "lead_outreach",
        "target": "SYSTEM",
        "description": "Workflow to run a lead outreach campaign",
        "product_type": "LeadOutreachCampaign",  # This must match the product_type in your Python model
    }
]


def upgrade() -> None:
    conn = op.get_bind()
    for workflow in new_workflows:
        create_workflow(conn, workflow)


def downgrade() -> None:
    conn = op.get_bind()
    for workflow in new_workflows:
        delete_workflow(conn, workflow["name"])
