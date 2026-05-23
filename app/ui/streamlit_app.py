"""Streamlit chatbot UI for the Loan Approval System.

Run with:
    streamlit run app/ui/streamlit_app.py
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st

from app.constants import EmploymentType, LoanDecision

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
EVAL_ENDPOINT = f"{API_BASE_URL.rstrip('/')}/api/v1/loan/evaluate"
HEALTH_ENDPOINT = f"{API_BASE_URL.rstrip('/')}/health"


def _badge(decision: str) -> str:
    """Render the decision as a coloured emoji badge."""
    return {
        LoanDecision.APPROVED.value: ":green[**APPROVED**]",
        LoanDecision.REJECTED.value: ":red[**REJECTED**]",
        LoanDecision.MANUAL_REVIEW.value: ":orange[**REQUIRES MANUAL REVIEW**]",
    }.get(decision, f"**{decision}**")


def _submit(payload: dict[str, Any]) -> dict[str, Any]:
    """POST the application to the FastAPI microservice."""
    with httpx.Client(timeout=120.0) as client:
        response = client.post(EVAL_ENDPOINT, json=payload)
    response.raise_for_status()
    return response.json()


def _check_api() -> bool:
    """Probe the FastAPI health endpoint."""
    try:
        with httpx.Client(timeout=3.0) as client:
            response = client.get(HEALTH_ENDPOINT)
            return response.status_code == 200
    except Exception:
        return False


def _render_result(data: dict[str, Any]) -> None:
    decision = data["loan_decision"]
    profile = data["applicant_profile"]
    risk = data["financial_risk"]
    compliance = data["compliance_action"]

    st.markdown(f"### Decision: {_badge(decision['classification'])}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Risk Score", f"{decision['risk_score']:.1f} / 100")
    col2.metric("Confidence", f"{decision['confidence_level'] * 100:.1f}%")
    col3.metric("Case ID", compliance["case_id"])

    with st.expander("Explanation", expanded=True):
        st.write(decision["explanation"])

    with st.expander("Key Decision Factors"):
        for factor in decision["key_decision_factors"]:
            st.markdown(f"- {factor}")

    tab_profile, tab_risk, tab_compliance, tab_trace = st.tabs(
        ["Applicant Profile", "Financial Risk", "Compliance Action", "Agent Trace"]
    )

    with tab_profile:
        st.json(profile)
    with tab_risk:
        st.json(risk)
    with tab_compliance:
        st.json(compliance)
    with tab_trace:
        st.markdown("**Agent execution trace**")
        for entry in data.get("agent_trace", []):
            st.markdown(f"- `{entry['agent']}` — {entry['elapsed_ms']} ms")


def _push_chat(role: str, content: str, extra: dict[str, Any] | None = None) -> None:
    st.session_state.chat_history.append({"role": role, "content": content, "extra": extra})


def _render_chat() -> None:
    for turn in st.session_state.chat_history:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])
            if turn.get("extra"):
                _render_result(turn["extra"])


def main() -> None:
    st.set_page_config(
        page_title="Intelligent Loan Approval",
        page_icon=":bank:",
        layout="wide",
    )

    st.title("Intelligent Loan Approval — Agentic AI")
    st.caption(
        "Submit a loan application. A multi-agent pipeline (Profile → Risk → Decision → Compliance) "
        "powered by LangGraph and Claude evaluates it end-to-end."
    )

    api_ok = _check_api()
    if api_ok:
        st.success(f"Connected to backend at {API_BASE_URL}")
    else:
        st.error(
            f"Backend at {API_BASE_URL} is not reachable. "
            "Start the FastAPI server with `uvicorn app.main:app`."
        )

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
        _push_chat(
            "assistant",
            "Hi! Fill in the application details in the sidebar and submit. "
            "I'll route it through the agent pipeline and report back.",
        )

    with st.sidebar:
        st.header("Loan Application")
        with st.form("loan_form", clear_on_submit=False):
            full_name = st.text_input("Full name", value="Asha Patel")
            age = st.number_input("Age", min_value=18, max_value=100, value=34, step=1)
            employment_type = st.selectbox(
                "Employment type",
                options=[e.value for e in EmploymentType],
                index=0,
            )
            income = st.number_input(
                "Annual income", min_value=0.0, value=950_000.0, step=10_000.0
            )
            credit_score = st.number_input(
                "Credit score", min_value=300, max_value=900, value=735, step=1
            )
            loan_amount = st.number_input(
                "Loan amount", min_value=0.0, value=1_500_000.0, step=50_000.0
            )
            loan_tenure_months = st.number_input(
                "Loan tenure (months)", min_value=12, max_value=360, value=60, step=12
            )
            existing_liabilities = st.number_input(
                "Existing liabilities (annual)", min_value=0.0, value=120_000.0, step=10_000.0
            )
            location = st.text_input("Location", value="Bengaluru, IN")
            purpose = st.text_input("Loan purpose", value="Home renovation")
            submitted = st.form_submit_button("Evaluate application", type="primary")

    if submitted:
        payload = {
            "full_name": full_name,
            "age": int(age),
            "employment_type": employment_type,
            "income": float(income),
            "credit_score": int(credit_score),
            "loan_amount": float(loan_amount),
            "loan_tenure_months": int(loan_tenure_months),
            "existing_liabilities": float(existing_liabilities),
            "location": location,
            "purpose": purpose or None,
        }
        _push_chat(
            "user",
            f"Please evaluate this application for **{full_name}** "
            f"(loan {loan_amount:,.0f} over {int(loan_tenure_months)} months).",
        )
        with st.spinner("Running multi-agent evaluation pipeline…"):
            try:
                response = _submit(payload)
            except httpx.HTTPError as exc:
                _push_chat(
                    "assistant",
                    f"Request failed: `{exc}`. Is the backend running at {API_BASE_URL}?",
                )
            else:
                if response.get("status") == "success":
                    data = response["data"]
                    decision = data["loan_decision"]["classification"]
                    _push_chat(
                        "assistant",
                        f"Pipeline complete — decision: {_badge(decision)}.",
                        extra=data,
                    )
                else:
                    _push_chat(
                        "assistant",
                        f"Workflow returned an error: `{response.get('message')}`.",
                    )

    _render_chat()


if __name__ == "__main__":
    main()
