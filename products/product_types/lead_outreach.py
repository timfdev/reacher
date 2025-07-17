from typing import ClassVar
from orchestrator.domain.base import SubscriptionModel
from orchestrator.workflow import Workflow

from products.product_blocks.lead_outreach_campaign_block import (
    LeadOutreachCampaignBlock,
)
from workflows.lead_outreach import lead_outreach


class LeadOutreachCampaign(
    SubscriptionModel, is_base=True, product_type="LeadOutreachCampaign"
):
    """Defines the Lead Outreach Campaign as a manageable product."""

    campaign_block: LeadOutreachCampaignBlock | None = None
    workflows: ClassVar[dict[str, Workflow]] = {"lead_outreach": lead_outreach}
