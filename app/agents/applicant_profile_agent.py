"""Applicant Profile Agent.

Backed by the ``ApplicantDB`` MCP server. Aggregates KYC, employment,
income-stability, and credit-history signals into an
``ApplicantProfileOutput``.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.constants import AgentName, MAX_APPLICANT_AGE, MIN_APPLICANT_AGE, RiskLevel
from app.models import ApplicantProfileOutput, LoanApplication
from app.services.mcp_client import call_mcp_tool
from app.services.mcp_servers.applicant_db import applicant_db_server


class ApplicantProfileAgent(BaseAgent):
    """Builds a holistic profile of the applicant."""

    def __init__(self) -> None:
        super().__init__(AgentName.APPLICANT_PROFILE)

    async def _run(self, context: dict[str, Any]) -> dict[str, Any]:
        application: LoanApplication = context["application"]
        app_dict = application.model_dump(mode="json")

        kyc = await call_mcp_tool(
            applicant_db_server,
            "fetch_kyc_status",
            {"applicant_id": application.applicant_id},
        )
        employment = await call_mcp_tool(
            applicant_db_server,
            "fetch_employment_history",
            {
                "applicant_id": application.applicant_id,
                "employment_type": application.employment_type.value,
            },
        )
        credit = await call_mcp_tool(
            applicant_db_server,
            "fetch_credit_history",
            {
                "applicant_id": application.applicant_id,
                "credit_score": application.credit_score,
            },
        )
        income = await call_mcp_tool(
            applicant_db_server,
            "fetch_income_stability",
            {
                "applicant_id": application.applicant_id,
                "income": application.income,
                "employment_type": application.employment_type.value,
            },
        )
        completeness = await call_mcp_tool(
            applicant_db_server,
            "check_application_completeness",
            {"application": app_dict},
        )

        flags = list(completeness.get("flags", []))
        if not kyc.get("kyc_verified", False):
            flags.append("warning:kyc_not_verified")

        eligible = (
            MIN_APPLICANT_AGE <= application.age <= MAX_APPLICANT_AGE
            and kyc.get("kyc_verified", False)
            and completeness.get("complete", True)
        )
        if application.age < MIN_APPLICANT_AGE:
            flags.append(f"ineligible:age_below_{MIN_APPLICANT_AGE}")
        elif application.age > MAX_APPLICANT_AGE:
            flags.append(f"ineligible:age_above_{MAX_APPLICANT_AGE}")

        profile = ApplicantProfileOutput(
            applicant_id=application.applicant_id,
            income_stability_score=income["income_stability_score"],
            employment_risk=RiskLevel(employment["employment_risk"]),
            credit_history_summary=credit["summary"],
            application_completeness_flags=flags,
            eligible=eligible,
            notes=(
                f"KYC verified: {kyc.get('kyc_verified', False)}; "
                f"employment tenure {employment['tenure_months']} months."
            ),
        )

        return {
            "profile": profile.model_dump(mode="json"),
            "raw": {
                "kyc": kyc,
                "employment": employment,
                "credit": credit,
                "income": income,
                "completeness": completeness,
            },
        }
