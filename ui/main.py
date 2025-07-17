import json
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st
from products.lead_models import Lead, LeadResult, REQUIRED_COLUMNS

from ui.config import Config


def start_workflow_for_lead(lead: Lead) -> Tuple[Optional[str], Optional[str]]:
    """Start a single workflow instance for a lead.

    Returns (process_id, error_message).
    """
    payload = [{"lead": lead.to_dict()}]
    url = Config.api_url(f"/api/processes/{Config.WORKFLOW_NAME}")
    try:
        resp = requests.post(url, json=payload)
    except Exception as e:  # network error
        return None, f"Network error: {e}"

    if resp.status_code not in (200, 201):
        return None, f"HTTP {resp.status_code}: {resp.text}"

    try:
        data = resp.json()
    except json.JSONDecodeError:
        return None, f"Invalid JSON in start response: {resp.text[:200]}"

    pid = data.get("id") or data.get("process_id")
    if not pid:
        return None, f"No process_id in start response: {data}"

    return pid, None


def fetch_process(pid: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Fetch a process JSON from Orchestrator."""
    url = Config.api_url(f"/api/processes/{pid}")
    try:
        resp = requests.get(url)
    except Exception as e:
        return None, f"Network error: {e}"

    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}: {resp.text}"

    try:
        data = resp.json()
    except json.JSONDecodeError:
        return None, f"Invalid JSON response: {resp.text[:200]}"

    return data, None


def resume_process(pid: str, approved: bool) -> Optional[str]:
    """Resume a suspended process with the approved flag."""
    url = Config.api_url(f"/api/processes/{pid}/resume")
    payload = [{"approved": approved}]
    try:
        resp = requests.put(url, json=payload)
    except Exception as e:
        return f"Network error: {e}"

    if resp.status_code != 204:  # API returns 204 No Content on success
        return f"HTTP {resp.status_code}: {resp.text}"
    return None


def abort_process(pid: str) -> Optional[str]:
    url = Config.api_url(f"/api/processes/{pid}/abort")
    try:
        resp = requests.post(url)
    except Exception as e:
        return f"Network error: {e}"
    if resp.status_code not in (200, 204):
        return f"HTTP {resp.status_code}: {resp.text}"
    return None


def wait_for_completion(
    pid: str,
    timeout: float = Config.POLL_TIMEOUT_SEC,
    interval: float = Config.POLL_INTERVAL_SEC,
) -> Optional[Dict[str, Any]]:
    """Poll process until it leaves running/suspended state or timeout.

    Returns final process JSON dict if detected, else None.
    """
    deadline = time.time() + timeout
    last_data = None
    while time.time() < deadline:
        data, err = fetch_process(pid)
        if err:
            return None
        last_data = data
        status = data.get("last_status")
        if status in ("completed", "failed", "aborted"):
            return data
        time.sleep(interval)
    return last_data  # Timed out; return last seen state (may still be running)


def extract_form_data(
    process_json: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract form schema + current_state values needed for the Review step.

    Returns (form_schema, current_state_dict).
    """
    return (
        process_json.get("form", {}) or {},
        process_json.get("current_state", {}) or {},
    )


def record_local_result(lead: Lead, approved: Optional[bool], status: str) -> None:
    """Store an outcome in session_state.results aligned to current_process_idx.

    If a result already recorded for this index, update it.
    """
    idx = st.session_state.current_process_idx
    # Ensure we have results list sized up to idx
    results = st.session_state.results
    while len(results) < idx:
        # pad missing rows with unknown for prior leads (shouldn't happen, but safe)
        prior_lead_dict = st.session_state.leads_data[len(results)]
        prior_lead = Lead.from_dict(prior_lead_dict)
        results.append(
            {"lead": prior_lead.to_dict(), "approved": None, "status": "unknown"}
        )

    new_entry = {"lead": lead.to_dict(), "approved": approved, "status": status}
    if len(results) == idx:
        results.append(new_entry)
    else:
        results[idx] = new_entry

    st.session_state.results = results


def fetch_process_result(pid: str, lead_dict: Dict[str, Any]) -> LeadResult:
    """Fetch authoritative final result for a process from the server."""
    lead = Lead.from_dict(lead_dict)
    data, err = fetch_process(pid)
    if err or not data:
        return LeadResult(lead=lead, approved=None, status=f"error ({err})")

    current_state = data.get("current_state", {}) or {}
    final_status = current_state.get("final_status")  # EXPECT: APPROVED | SKIPPED

    if final_status == "APPROVED":
        return LeadResult(lead=lead, approved=True, status="APPROVED")
    if final_status == "SKIPPED":
        return LeadResult(lead=lead, approved=False, status="SKIPPED")

    # Fallback: use last_status when final_status missing
    last_status = data.get("last_status", "unknown")
    approved: Optional[bool]
    if last_status == "completed":
        approved = None  # Completed but we can't tell how it resolved
    elif last_status in ("failed", "aborted"):
        approved = False
    else:
        approved = None
    return LeadResult(lead=lead, approved=approved, status=last_status)


def sync_all_results_from_server() -> List[LeadResult]:
    """Fetch & overwrite session_state.results from the server for every process."""
    results: List[LeadResult] = []
    for pid, lead_dict in zip(
        st.session_state.process_ids, st.session_state.leads_data
    ):
        results.append(fetch_process_result(pid, lead_dict))
    st.session_state.results = [
        r.to_row() for r in results
    ]  # store as serializable dicts
    return results


def results_to_dataframe(results: List[LeadResult]) -> pd.DataFrame:
    return pd.DataFrame([r.to_row() for r in results])


def sidebar_status() -> None:
    """Sidebar: show campaign status + cancel button."""
    with st.sidebar:
        st.header("Campaign Status")
        leads = st.session_state.leads_data
        pids = st.session_state.process_ids
        if pids:
            st.info(f"Total Leads: {len(leads)}")
            current_idx = st.session_state.current_process_idx
            current_lead_num = min(current_idx + 1, len(leads)) if leads else 0
            st.info(f"Current Lead: {current_lead_num}")
            if leads:
                progress = current_lead_num / len(leads)
                progress = min(progress, 1.0)
                st.progress(progress)

            if st.button("❌ Cancel All Workflows"):
                for pid in pids:
                    abort_process(pid)
                # reset state
                st.session_state.process_ids = []
                st.session_state.workflow_state = Config.STATE_IDLE
                st.session_state.current_process_idx = 0
                st.session_state.leads_data = []
                st.session_state.results = []
                st.rerun()
        else:
            st.caption("No active campaign.")


def render_idle_state():
    """Render upload/start UI when no campaign active."""
    st.header("Start New Outreach Campaign")
    uploaded_file = st.file_uploader(
        "Upload Leads CSV",
        type=["csv"],
        help=f"CSV must contain columns: {', '.join(REQUIRED_COLUMNS)}",
    )
    if not uploaded_file:
        return

    # Display preview
    try:
        df = pd.read_csv(uploaded_file)
    except Exception as e:  # decode error
        st.error(f"Failed to read CSV: {e}")
        return

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        st.error(f"CSV missing required column(s): {missing}")
        return

    st.subheader("CSV Preview")
    st.dataframe(df.head())
    st.info(f"Total leads to process: {len(df)}")

    # Because reading file consumes pointer, reopen fresh copy on start.
    uploaded_file.seek(0)

    if st.button("🚀 Start Workflows", type="primary"):
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file)
        leads_list = df.to_dict("records")
        st.session_state.leads_data = leads_list

        progress_bar = st.progress(0.0)
        status_text = st.empty()
        process_ids: List[str] = []
        errors: List[str] = []

        for idx, lead_dict in enumerate(leads_list):
            lead = Lead.from_dict(lead_dict)
            status_text.text(f"Starting workflow for {lead.name}...")
            pid, err = start_workflow_for_lead(lead)
            if pid:
                process_ids.append(pid)
            else:
                errors.append(f"Failed for {lead.name}: {err}")
            progress_bar.progress((idx + 1) / len(leads_list))

        if process_ids:
            st.session_state.process_ids = process_ids
            st.session_state.workflow_state = Config.STATE_RUNNING
            st.session_state.current_process_idx = 0
            st.session_state.results = []  # reset results
            st.success(f"✅ Started {len(process_ids)} workflows!")

            if errors:
                with st.expander("⚠️ Some workflows failed to start"):
                    for error in errors:
                        st.error(error)

            time.sleep(1.5)
            st.rerun()
        else:
            st.error("Failed to start any workflows.")


def render_suspended_state(
    process_json: Dict[str, Any], pid: str, lead_dict: Dict[str, Any]
):
    """UI for suspended process awaiting review."""
    lead = Lead.from_dict(lead_dict)
    form_schema, current_state = extract_form_data(process_json)

    # Extract context fields gracefully
    context = current_state.get("scraped_context", "N/A")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.write(f"**Name:** {lead.name}")
        st.write(f"**Email:** {lead.email}")
        st.write(f"**Website:** {lead.website}")
        st.write(f"**Context:** {context}")

    def _handle_decision(approved: bool) -> None:
        err = resume_process(pid, approved=approved)
        if err:
            st.error(f"Resume failed: {err}")
            return

        # Poll for completion if configured
        if Config.POLL_AFTER_RESUME:
            _ = wait_for_completion(
                pid
            )  # we don't need the data now; summary re-fetches later

        # Optimistically record and advance
        record_local_result(
            lead, approved=approved, status=("APPROVED" if approved else "SKIPPED")
        )
        if approved:
            st.success("Approved!")
        else:
            st.info("Skipped.")

        time.sleep(0.5)
        st.session_state.current_process_idx += 1
        st.rerun()

    with col2:
        if st.button("✅ Approve", type="primary", use_container_width=True):
            _handle_decision(True)
        if st.button("⏭️ Skip", use_container_width=True):
            _handle_decision(False)


def render_running_state():
    """Render the per-lead processing UI while campaign active."""
    pids = st.session_state.process_ids
    leads = st.session_state.leads_data
    idx = st.session_state.current_process_idx

    # Guard: if something went wrong and no pids, drop to idle
    if not pids or idx >= len(pids):
        st.session_state.workflow_state = Config.STATE_DONE
        st.rerun()
        return

    current_pid = pids[idx]
    current_lead_dict = leads[idx]
    lead = Lead.from_dict(current_lead_dict)

    st.header(f"Processing Lead {idx + 1} of {len(leads)}")
    st.subheader(f"Current: {lead.name}")

    process_json, err = fetch_process(current_pid)
    if err or not process_json:
        st.error(f"Error fetching process: {err}")
        if st.button("⏭️ Skip to Next"):
            record_local_result(lead, approved=None, status="error")
            st.session_state.current_process_idx += 1
            st.rerun()
        return

    last_status = process_json.get("last_status", "unknown")

    # Suspended -> show form
    if last_status == "suspended" and process_json.get("form"):
        render_suspended_state(process_json, current_pid, current_lead_dict)
        return

    # Terminal states -> record and advance automatically
    if last_status in ("completed", "failed", "aborted"):
        current_state = process_json.get("current_state", {}) or {}
        final_status = current_state.get("final_status")
        if final_status == "APPROVED":
            approved = True
            status = "APPROVED"
        elif final_status == "SKIPPED":
            approved = False
            status = "SKIPPED"
        else:
            # fallback: based on last_status
            approved = None if last_status == "completed" else False
            status = last_status

        record_local_result(lead, approved=approved, status=status)
        time.sleep(0.5)
        st.session_state.current_process_idx += 1
        st.rerun()
        return

    # Otherwise still running
    st.info(f"Processing... (Status: {last_status})")
    # Light auto-refresh while waiting
    time.sleep(1.5)
    st.rerun()


def render_summary_state():
    """Render final campaign summary once all leads handled."""
    st.success("🎉 All leads processed!")

    # Always re-fetch authoritative results from server.
    results: List[LeadResult] = sync_all_results_from_server()

    # Convert dict forms in session_state back to dataclass for convenience when building metrics
    lead_results: List[LeadResult] = []
    for r in st.session_state.results:  # each r is serializable dict
        lead = Lead.from_dict(r)

        lead_results.append(
            LeadResult(
                lead=lead, approved=r.get("approved"), status=r.get("status", "unknown")
            )
        )

    df_summary = results_to_dataframe(results)

    total = len(df_summary)
    approved_count = df_summary["Approved?"].fillna(False).astype(bool).sum()
    skipped_count = (df_summary["Status"] == "SKIPPED").sum()
    error_count = (
        df_summary["Status"]
        .astype(str)
        .str.contains("error", case=False, na=False)
        .sum()
    )

    st.header("Campaign Summary")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Leads", total)
    with c2:
        st.metric("Approved", int(approved_count))
    with c3:
        st.metric("Skipped", int(skipped_count))
    with c4:
        st.metric("Errors", int(error_count))

    st.dataframe(df_summary, use_container_width=True)

    # CSV download
    csv_bytes = df_summary.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download Summary CSV",
        data=csv_bytes,
        file_name="lead_outreach_summary.csv",
        mime="text/csv",
    )

    if st.button("🔄 Start New Campaign", type="primary"):
        # Full reset
        st.session_state.process_ids = []
        st.session_state.workflow_state = Config.STATE_IDLE
        st.session_state.current_process_idx = 0
        st.session_state.leads_data = []
        st.session_state.results = []
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="Lead Outreach Workflow", layout="wide")
    st.title("📧 Lead Outreach Workflow")

    Config.init_session_state()
    sidebar_status()

    state = st.session_state.workflow_state

    # Determine state transitions
    if state == Config.STATE_IDLE:
        render_idle_state()
    elif state == Config.STATE_RUNNING:
        # If we've processed all pids, transition to done
        if st.session_state.current_process_idx >= len(st.session_state.process_ids):
            st.session_state.workflow_state = Config.STATE_DONE
            st.rerun()
        else:
            render_running_state()
    elif state == Config.STATE_DONE:
        render_summary_state()
    else:
        st.warning(f"Unknown workflow_state: {state}. Resetting.")
        st.session_state.workflow_state = Config.STATE_IDLE
        st.rerun()


if __name__ == "__main__":
    main()
