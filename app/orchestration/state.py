"""LangGraph state schema for the loan workflow."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

import operator

from app.models import LoanApplication


class LoanWorkflowState(TypedDict, total=False):
    """State carried between LangGraph nodes.

    Each domain agent appends a trace entry to ``agent_trace`` (merged via the
    ``operator.add`` reducer) and stores its structured output under a node-
    specific key so downstream nodes can read it without rerunning work.
    """

    application: LoanApplication
    applicant_profile_trace: dict[str, Any]
    financial_risk_trace: dict[str, Any]
    loan_decision_trace: dict[str, Any]
    compliance_trace: dict[str, Any]
    agent_trace: Annotated[list[dict[str, Any]], operator.add]
    error: str | None
