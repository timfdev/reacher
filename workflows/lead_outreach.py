from typing import Dict

from orchestrator.config.assignee import Assignee
from orchestrator.forms import FormPage
from orchestrator.types import State
from orchestrator.targets import Target
from orchestrator.workflow import StepList, begin, done, inputstep, step, workflow
from pydantic_forms.types import FormGenerator

from products.lead_models import Lead


def initial_input_form_generator() -> FormGenerator:
    class StartForm(FormPage):
        lead: Dict[str, str]

    user_input = yield StartForm
    return user_input.model_dump()


@step("Scrape website for context")
def scrape_website(lead: Lead) -> State:
    print(f"Pretending to scrape website for {lead.get('name')}...")
    return {"scraped_context": "This company sells high-quality artisanal widgets."}


@inputstep("Review Lead", assignee=Assignee.SYSTEM)
def review_lead(lead: Dict[str, str], scraped_context: str) -> FormGenerator:
    context = scraped_context

    class ReviewForm(FormPage):
        name: str = lead.get("name", "")
        email: str = lead.get("email", "")
        website: str = lead.get("website", "")
        scraped_context: str = context
        approved: bool | None = None

    user_input = yield ReviewForm
    return {
        "approved": user_input.approved if user_input.approved is not None else False
    }


@step("Log Approval Status")
def log_approval(approved: bool, lead: Dict[str, str]) -> State:
    status = "APPROVED" if approved else "SKIPPED"
    print(f"Lead '{lead.get('name')}' ({lead.get('email')}) was {status}")
    return {"final_status": status}


@workflow(
    "lead_outreach",
    initial_input_form=initial_input_form_generator,
    target=Target.SYSTEM,
)
def lead_outreach() -> StepList:
    return begin >> scrape_website >> review_lead >> log_approval >> done
