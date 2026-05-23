"""Compliance & Action Orchestrator Agent.

Backed by the ``NotificationSystem`` MCP server. Performs the post-decision
side-effects: persists the case, sends notifications, and records the audit
trail.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.agents.base import BaseAgent
from app.constants import AgentName
from app.models import ComplianceActionOutput, LoanApplication
from app.services.mcp_client import call_mcp_tool
from app.services.mcp_servers.notification_system import notification_server


class ComplianceActionAgent(BaseAgent):
    """Carries out the action implied by the decision."""

    def __init__(self) -> None:
        super().__init__(AgentName.COMPLIANCE)

    async def _run(self, context: dict[str, Any]) -> dict[str, Any]:
        application: LoanApplication = context["application"]
        decision = context["loan_decision_trace"]["output"]["decision"]

        case = await call_mcp_tool(
            notification_server,
            "create_case",
            {
                "applicant_id": application.applicant_id,
                "classification": decision["classification"],
                "risk_score": decision["risk_score"],
                "explanation": decision["explanation"],
            },
        )
        action = await call_mcp_tool(
            notification_server,
            "determine_action",
            {"classification": decision["classification"]},
        )
        notification = await call_mcp_tool(
            notification_server,
            "send_notification",
            {
                "applicant_id": application.applicant_id,
                "classification": decision["classification"],
                "case_id": case["case_id"],
                "explanation": decision["explanation"],
                "channel": "email",
            },
        )

        compliance = ComplianceActionOutput(
            applicant_id=application.applicant_id,
            case_id=case["case_id"],
            action_taken=action["action_taken"],
            notification_sent=bool(notification.get("delivered")),
            notification_channel=notification["channel"],
            timestamp=datetime.utcnow(),
            summary=(
                f"Decision '{decision['classification']}' recorded as case "
                f"{case['case_id']}. {action['action_taken']} "
                f"Notification dispatched via {notification['channel']}."
            ),
        )

        return {
            "compliance_action": compliance.model_dump(mode="json"),
            "raw": {
                "case": case,
                "action": action,
                "notification": notification,
            },
        }
