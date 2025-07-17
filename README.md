# Reacher

A simple Streamlit app using WorkFlowOrchestrator to personalize lead outreach for mail/linkedin.

## 🚀 Quick Start

1. **Install dependencies**

   ```bash
   poetry install
   ```

2. **Run Orchestrator & dependencies**

   ```bash
   docker compose up --build
   ```

3. **Start the Streamlit UI**

   ```bash
   poetry run streamlit run ui/main.py
   ```

4. Open your browser at **http://localhost:8501**.

## Features

- Upload a CSV of leads (`name`, `email`, `website`).
- Kick off the `lead_outreach` workflow for each lead.
- Review & approve/skip leads in the ui.
- View summary & download results as CSV.

---
