# products/shared/lead_models.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional

import pandas as pd


@dataclass(slots=True)
class Lead:
    """Canonical lead record shared by workflow + UI."""

    name: str
    email: str
    website: str

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Lead":
        return cls(
            name=str(d.get("name", "")).strip(),
            email=str(d.get("email", "")).strip(),
            website=str(d.get("website", "")).strip(),
        )

    @classmethod
    def from_any(cls, obj: Any) -> "Lead":
        """Best-effort conversion from Lead, mapping, or attr-like object."""
        if isinstance(obj, cls):
            return obj
        if isinstance(obj, Mapping):
            return cls.from_dict(obj)
        return cls(
            name=str(getattr(obj, "name", "")).strip(),
            email=str(getattr(obj, "email", "")).strip(),
            website=str(getattr(obj, "website", "")).strip(),
        )

    def to_dict(self) -> Dict[str, str]:
        return {"name": self.name, "email": self.email, "website": self.website}

    def to_api_payload(self) -> Dict[str, Dict[str, str]]:
        """Shape expected by POST /api/processes/<workflow>."""
        return {"lead": self.to_dict()}


@dataclass(slots=True)
class LeadResult:
    lead: Lead
    approved: Optional[bool]
    status: str

    def to_row(self) -> Dict[str, Any]:
        return {
            "Name": self.lead.name,
            "Email": self.lead.email,
            "Website": self.lead.website,
            "Approved?": self.approved,
            "Status": self.status,
        }

    @classmethod
    def from_process_json(
        cls, lead_like: Any, process_json: Mapping[str, Any]
    ) -> "LeadResult":
        """Derive LeadResult from Orchestrator process JSON blob."""
        lead = Lead.from_any(lead_like)
        cs = (process_json.get("current_state") or {}) if process_json else {}
        final_status = cs.get("final_status")
        last_status = process_json.get("last_status") if process_json else None

        if final_status == "APPROVED":
            return cls(lead=lead, approved=True, status="APPROVED")
        if final_status == "SKIPPED":
            return cls(lead=lead, approved=False, status="SKIPPED")

        if last_status in ("failed", "aborted"):
            return cls(lead=lead, approved=False, status=last_status or "unknown")
        if last_status == "completed":
            return cls(lead=lead, approved=None, status="completed")

        return cls(lead=lead, approved=None, status=last_status or "unknown")


LeadDict = Dict[str, str]
REQUIRED_COLUMNS = ["name", "email", "website"]


def ensure_lead_dict(obj: Any) -> LeadDict:
    """Always return a LeadDict suitable for API calls."""
    if isinstance(obj, Lead):
        return obj.to_dict()
    if isinstance(obj, Mapping):
        return Lead.from_dict(obj).to_dict()
    return Lead.from_any(obj).to_dict()


def leads_from_dataframe(df: pd.DataFrame) -> List[LeadDict]:
    """Validate & convert a DataFrame of leads into list-of-dicts."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return (
        df[REQUIRED_COLUMNS]
        .astype(str)
        .apply(lambda s: s.str.strip())
        .to_dict("records")
    )


def leads_to_dataframe(leads: Iterable[Lead | Mapping[str, Any]]) -> pd.DataFrame:
    rows = [ensure_lead_dict(lead) for lead in leads]
    return pd.DataFrame(rows, columns=REQUIRED_COLUMNS)
