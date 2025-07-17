import os


class Config:

    # Configuration
    ORCHESTRATOR_BASE = os.getenv("ORCH_BASE", "http://localhost:8080")
    WORKFLOW_NAME = os.getenv("ORCH_WORKFLOW", "lead_outreach")

    POLL_AFTER_RESUME = True  # Wait briefly for workflow to finish after Approve/Skip
    POLL_TIMEOUT_SEC = 8  # Max seconds to wait after resume
    POLL_INTERVAL_SEC = 0.5  # Poll interval while waiting

    STATE_IDLE = "idle"
    STATE_RUNNING = "running"
    STATE_DONE = "done"

    @staticmethod
    def init_session_state() -> None:
        try:
            import streamlit as st
        except ImportError:
            return
        """Ensure all keys exist in st.session_state."""
        ss = st.session_state
        ss.setdefault("process_ids", [])
        ss.setdefault("workflow_state", Config.STATE_IDLE)
        ss.setdefault("current_process_idx", 0)
        ss.setdefault("leads_data", [])
        ss.setdefault("results", [])

    @staticmethod
    def api_url(path: str) -> str:
        return f"{Config.ORCHESTRATOR_BASE.rstrip('/')}{path}"
