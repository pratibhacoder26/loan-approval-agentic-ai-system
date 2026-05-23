"""Financial Risk Analysis Agent.

Backed by the ``RiskRulesDB`` MCP server. Computes the quantitative side of
the assessment (DTI, credit risk, loan-amount risk, anomalies) and asks the
LLM for a short natural-language rationale that wraps the numbers.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.constants import AgentName, RiskLevel
from app.models import FinancialRiskOutput, LoanApplication
from app.services.llm_service import get_llm_service
from app.services.mcp_client import call_mcp_tool
from app.services.mcp_servers.risk_rules_db import risk_rules_server

_REASONING_SYSTEM = (
    "You are a senior credit risk analyst. Given quantitative risk signals "
    "for a loan application, produce a concise (<=120 words) explanation in "
    "plain English. Cite specific numbers. Do not invent data. Output prose "
    "only — no headings, no bullet lists."
)


class FinancialRiskAnalysisAgent(BaseAgent):
    """Quantitative risk assessment plus LLM-authored reasoning."""

    def __init__(self) -> None:
        super().__init__(AgentName.FINANCIAL_RISK)

    async def _run(self, context: dict[str, Any]) -> dict[str, Any]:
        application: LoanApplication = context["application"]
        profile_trace = context["applicant_profile_trace"]["output"]
        profile = profile_trace["profile"]
        employment_risk = profile["employment_risk"]

        dti = await call_mcp_tool(
            risk_rules_server,
            "compute_debt_to_income",
            {
                "income": application.income,
                "existing_liabilities": application.existing_liabilities,
                "loan_amount": application.loan_amount,
                "loan_tenure_months": application.loan_tenure_months,
            },
        )
        credit = await call_mcp_tool(
            risk_rules_server,
            "classify_credit_score",
            {"credit_score": application.credit_score},
        )
        loan_amt = await call_mcp_tool(
            risk_rules_server,
            "classify_loan_amount",
            {
                "loan_amount": application.loan_amount,
                "income": application.income,
            },
        )
        anomalies = await call_mcp_tool(
            risk_rules_server,
            "detect_anomalies",
            {"application": application.model_dump(mode="json")},
        )
        composite = await call_mcp_tool(
            risk_rules_server,
            "composite_risk_score",
            {
                "dti_band": dti["dti_risk_band"],
                "credit_band": credit["credit_score_risk_level"],
                "loan_amount_band": loan_amt["loan_amount_risk"],
                "employment_risk": employment_risk,
                "anomaly_detected": anomalies["anomaly_detected"],
            },
        )

        reasoning = await self._build_reasoning(
            application=application,
            dti=dti,
            credit=credit,
            loan_amt=loan_amt,
            anomalies=anomalies,
            composite=composite,
            employment_risk=employment_risk,
        )

        risk = FinancialRiskOutput(
            applicant_id=application.applicant_id,
            debt_to_income_ratio=dti["debt_to_income_ratio"],
            credit_score_risk_level=RiskLevel(credit["credit_score_risk_level"]),
            loan_amount_risk=RiskLevel(loan_amt["loan_amount_risk"]),
            anomaly_detected=anomalies["anomaly_detected"],
            anomaly_reasons=anomalies.get("anomaly_reasons", []),
            composite_risk_score=composite["composite_risk_score"],
            reasoning=reasoning,
        )

        return {
            "financial_risk": risk.model_dump(mode="json"),
            "raw": {
                "dti": dti,
                "credit": credit,
                "loan_amt": loan_amt,
                "anomalies": anomalies,
                "composite": composite,
            },
        }

    async def _build_reasoning(
        self,
        *,
        application: LoanApplication,
        dti: dict[str, Any],
        credit: dict[str, Any],
        loan_amt: dict[str, Any],
        anomalies: dict[str, Any],
        composite: dict[str, Any],
        employment_risk: str,
    ) -> str:
        """Ask the LLM for a brief natural-language rationale."""
        llm = await get_llm_service()
        prompt = (
            "Loan application risk signals:\n"
            f"- Applicant ID: {application.applicant_id}\n"
            f"- Income (annual): {application.income:,.2f}\n"
            f"- Loan amount: {application.loan_amount:,.2f}\n"
            f"- Tenure (months): {application.loan_tenure_months}\n"
            f"- Estimated monthly EMI: {dti['estimated_monthly_emi']:,.2f}\n"
            f"- Debt-to-income ratio: {dti['debt_to_income_ratio']:.2f} ({dti['dti_risk_band']})\n"
            f"- Credit score: {application.credit_score} ({credit['credit_score_risk_level']})\n"
            f"- Loan amount risk: {loan_amt['loan_amount_risk']} "
            f"(income multiple {loan_amt['income_multiple']}×)\n"
            f"- Employment risk: {employment_risk}\n"
            f"- Anomaly detected: {anomalies['anomaly_detected']}; "
            f"reasons: {anomalies.get('anomaly_reasons', [])}\n"
            f"- Composite risk score: {composite['composite_risk_score']}/100\n\n"
            "Write the analyst rationale now."
        )
        try:
            return await llm.complete(_REASONING_SYSTEM, prompt, max_tokens=320)
        except Exception:  # pragma: no cover - fall back to deterministic text
            return (
                f"Composite risk score is {composite['composite_risk_score']}/100. "
                f"DTI {dti['debt_to_income_ratio']:.2f} ({dti['dti_risk_band']}); "
                f"credit score {application.credit_score} "
                f"({credit['credit_score_risk_level']}); "
                f"loan amount risk {loan_amt['loan_amount_risk']}; "
                f"employment risk {employment_risk}. "
                f"Anomalies: {anomalies.get('anomaly_reasons') or 'none'}."
            )
