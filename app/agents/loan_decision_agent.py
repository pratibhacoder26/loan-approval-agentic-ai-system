"""Loan Decision Agent.

Synthesises the upstream agent outputs into the final decision. Uses the
``DecisionSynthesis`` MCP server for deterministic banding and confidence,
then asks the LLM to author a final, applicant-facing explanation that
references the concrete factors.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.constants import AgentName, LoanDecision
from app.models import LoanApplication, LoanDecisionOutput
from app.services.llm_service import get_llm_service
from app.services.mcp_client import call_mcp_tool
from app.services.mcp_servers.decision_synthesis import decision_synthesis_server

_EXPLANATION_SYSTEM = (
    "You are a senior loan officer producing applicant-facing rationale for "
    "an automated decision. Strict requirements: 80-150 words, second-person "
    "tone ('your application…'), reference specific numbers from the inputs, "
    "do not invent any data. End with one sentence on next steps appropriate "
    "to the decision (Approved / Rejected / Requires Manual Review)."
)


class LoanDecisionAgent(BaseAgent):
    """Final classification, confidence and explanation."""

    def __init__(self) -> None:
        super().__init__(AgentName.LOAN_DECISION)

    async def _run(self, context: dict[str, Any]) -> dict[str, Any]:
        application: LoanApplication = context["application"]
        profile = context["applicant_profile_trace"]["output"]["profile"]
        risk = context["financial_risk_trace"]["output"]["financial_risk"]
        risk_raw = context["financial_risk_trace"]["output"]["raw"]

        classification = await call_mcp_tool(
            decision_synthesis_server,
            "classify_application",
            {
                "composite_risk_score": risk["composite_risk_score"],
                "anomaly_detected": risk["anomaly_detected"],
                "eligible": profile["eligible"],
                "completeness_complete": not any(
                    f.startswith("missing:") for f in profile["application_completeness_flags"]
                ),
            },
        )
        confidence = await call_mcp_tool(
            decision_synthesis_server,
            "compute_confidence",
            {
                "composite_risk_score": risk["composite_risk_score"],
                "anomaly_detected": risk["anomaly_detected"],
                "employment_risk": profile["employment_risk"],
                "credit_band": risk["credit_score_risk_level"],
            },
        )
        factors = await call_mcp_tool(
            decision_synthesis_server,
            "extract_key_factors",
            {
                "dti": risk["debt_to_income_ratio"],
                "dti_band": risk_raw["dti"]["dti_risk_band"],
                "credit_score": application.credit_score,
                "credit_band": risk["credit_score_risk_level"],
                "loan_amount_risk": risk["loan_amount_risk"],
                "employment_risk": profile["employment_risk"],
                "income_stability_score": profile["income_stability_score"],
                "anomaly_reasons": risk["anomaly_reasons"],
            },
        )

        explanation = await self._build_explanation(
            application=application,
            classification=classification["classification"],
            risk_score=risk["composite_risk_score"],
            factors=factors["key_decision_factors"],
            profile=profile,
            risk=risk,
        )

        decision = LoanDecisionOutput(
            applicant_id=application.applicant_id,
            classification=LoanDecision(classification["classification"]),
            risk_score=risk["composite_risk_score"],
            confidence_level=confidence["confidence_level"],
            key_decision_factors=factors["key_decision_factors"],
            explanation=explanation,
        )

        return {
            "decision": decision.model_dump(mode="json"),
            "raw": {
                "classification": classification,
                "confidence": confidence,
                "factors": factors,
            },
        }

    async def _build_explanation(
        self,
        *,
        application: LoanApplication,
        classification: str,
        risk_score: float,
        factors: list[str],
        profile: dict[str, Any],
        risk: dict[str, Any],
    ) -> str:
        llm = await get_llm_service()
        prompt = (
            f"Decision: {classification}\n"
            f"Applicant ID: {application.applicant_id}\n"
            f"Name: {application.full_name}\n"
            f"Composite risk score: {risk_score}/100\n"
            f"Income stability score: {profile['income_stability_score']}/100\n"
            f"Credit score: {application.credit_score}\n"
            f"Loan amount requested: {application.loan_amount:,.2f}\n"
            f"Tenure: {application.loan_tenure_months} months\n"
            f"Employment: {application.employment_type.value}\n"
            f"Existing liabilities: {application.existing_liabilities:,.2f}\n"
            "Key decision factors:\n- " + "\n- ".join(factors) + "\n"
            f"Risk reasoning: {risk['reasoning']}\n\n"
            "Write the explanation now."
        )
        try:
            return await llm.complete(_EXPLANATION_SYSTEM, prompt, max_tokens=400)
        except Exception:  # pragma: no cover
            return (
                f"Your application has been classified as {classification}. "
                f"Composite risk score is {risk_score}/100. "
                f"Driving factors: {'; '.join(factors[:4])}. "
                + {
                    LoanDecision.APPROVED.value: "Disbursement will be initiated.",
                    LoanDecision.REJECTED.value: "You may reapply after addressing the cited concerns.",
                    LoanDecision.MANUAL_REVIEW.value: "An underwriter will follow up shortly.",
                }.get(classification, "")
            )
