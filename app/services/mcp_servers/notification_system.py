"""NotificationSystem MCP server.

Backs the Compliance & Action Orchestrator Agent. Persists a case record,
emits a notification (email / SMS / chat — simulated here), and returns the
audit trail.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastmcp import FastMCP

from app.constants import LoanDecision, MCPServerName

logger = logging.getLogger(__name__)

notification_server = FastMCP(name=MCPServerName.NOTIFICATION_SYSTEM.value)


# In-memory case ledger. In production this is a durable store (Postgres, etc.).
_CASE_LEDGER: dict[str, dict[str, Any]] = {}


@notification_server.tool
def create_case(
    applicant_id: str,
    classification: str,
    risk_score: float,
    explanation: str,
) -> dict[str, Any]:
    """Persist a case record and return its identifier."""
    case_id = f"CASE-{uuid4().hex[:12].upper()}"
    record = {
        "case_id": case_id,
        "applicant_id": applicant_id,
        "classification": classification,
        "risk_score": risk_score,
        "explanation": explanation,
        "created_at": datetime.utcnow().isoformat(),
    }
    _CASE_LEDGER[case_id] = record
    logger.info("Case created: %s for applicant %s", case_id, applicant_id)
    return record


@notification_server.tool
def send_notification(
    applicant_id: str,
    classification: str,
    case_id: str,
    explanation: str,
    channel: str = "email",
) -> dict[str, Any]:
    """Send the applicant a notification appropriate to the decision."""
    subject_map = {
        LoanDecision.APPROVED.value: "Your loan application has been approved",
        LoanDecision.REJECTED.value: "Update on your loan application",
        LoanDecision.MANUAL_REVIEW.value: "Your loan application is under review",
    }
    subject = subject_map.get(classification, "Loan application update")
    body = (
        f"Dear applicant ({applicant_id}),\n\n"
        f"Your application (case {case_id}) has been classified as: {classification}.\n\n"
        f"Summary:\n{explanation}\n\n"
        "Thank you for choosing our services."
    )

    logger.info(
        "Dispatched %s notification to %s via %s (case %s)",
        classification,
        applicant_id,
        channel,
        case_id,
    )

    return {
        "applicant_id": applicant_id,
        "case_id": case_id,
        "channel": channel,
        "subject": subject,
        "body": body,
        "sent_at": datetime.utcnow().isoformat(),
        "delivered": True,
    }


@notification_server.tool
def determine_action(classification: str) -> dict[str, Any]:
    """Return the canonical downstream action for a given decision."""
    actions = {
        LoanDecision.APPROVED.value: "Approved — disbursement workflow initiated.",
        LoanDecision.REJECTED.value: "Rejected — applicant notified with reasons.",
        LoanDecision.MANUAL_REVIEW.value: "Escalated to underwriter queue for manual review.",
    }
    return {
        "classification": classification,
        "action_taken": actions.get(classification, "No action taken."),
    }


@notification_server.tool
def fetch_case(case_id: str) -> dict[str, Any]:
    """Look up a previously created case."""
    record = _CASE_LEDGER.get(case_id)
    if record is None:
        return {"case_id": case_id, "found": False}
    return {"found": True, **record}
