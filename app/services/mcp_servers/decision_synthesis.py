"""DecisionSynthesis MCP server.

Backs the Loan Decision Agent. Provides deterministic classification logic
(used as a guardrail) and confidence scoring on top of the upstream agent
outputs.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from app.constants import (
    LoanDecision,
    MCPServerName,
    RISK_APPROVE_MAX,
    RISK_REVIEW_MAX,
    RiskLevel,
)

decision_synthesis_server = FastMCP(name=MCPServerName.DECISION_SYNTHESIS.value)


@decision_synthesis_server.tool
def classify_application(
    composite_risk_score: float,
    anomaly_detected: bool,
    eligible: bool,
    completeness_complete: bool,
) -> dict[str, Any]:
    """Translate aggregated risk signals into a final decision band."""
    if not eligible or not completeness_complete:
        return {
            "classification": LoanDecision.MANUAL_REVIEW.value,
            "reason_code": "INELIGIBLE_OR_INCOMPLETE",
        }
    if anomaly_detected and composite_risk_score >= RISK_APPROVE_MAX:
        return {
            "classification": LoanDecision.MANUAL_REVIEW.value,
            "reason_code": "ANOMALY_REQUIRES_REVIEW",
        }
    if composite_risk_score <= RISK_APPROVE_MAX:
        return {
            "classification": LoanDecision.APPROVED.value,
            "reason_code": "LOW_RISK_APPROVAL",
        }
    if composite_risk_score <= RISK_REVIEW_MAX:
        return {
            "classification": LoanDecision.MANUAL_REVIEW.value,
            "reason_code": "MEDIUM_RISK_REVIEW",
        }
    return {
        "classification": LoanDecision.REJECTED.value,
        "reason_code": "HIGH_RISK_REJECTION",
    }


@decision_synthesis_server.tool
def compute_confidence(
    composite_risk_score: float,
    anomaly_detected: bool,
    employment_risk: str,
    credit_band: str,
) -> dict[str, Any]:
    """Express how confident we are in the deterministic classification.

    Confidence is highest at the extremes of the risk scale and lowest near
    the band boundaries. Anomalies and elevated employment / credit risk drag
    confidence down.
    """
    # Distance from the nearest boundary in [0, 100].
    nearest = min(
        abs(composite_risk_score - RISK_APPROVE_MAX),
        abs(composite_risk_score - RISK_REVIEW_MAX),
        composite_risk_score,
        100 - composite_risk_score,
    )
    confidence = min(0.99, 0.55 + (nearest / 100.0) * 0.8)

    if anomaly_detected:
        confidence -= 0.10
    if employment_risk in {RiskLevel.HIGH.value, RiskLevel.CRITICAL.value}:
        confidence -= 0.05
    if credit_band in {RiskLevel.HIGH.value, RiskLevel.CRITICAL.value}:
        confidence -= 0.05

    confidence = max(0.30, min(0.99, confidence))
    return {"confidence_level": round(confidence, 3)}


@decision_synthesis_server.tool
def extract_key_factors(
    dti: float,
    dti_band: str,
    credit_score: int,
    credit_band: str,
    loan_amount_risk: str,
    employment_risk: str,
    income_stability_score: float,
    anomaly_reasons: list[str],
) -> dict[str, Any]:
    """Surface the top decision-driving factors in user-friendly text."""
    factors: list[str] = [
        f"Credit score {credit_score} ({credit_band} risk).",
        f"Debt-to-income ratio {dti:.2f} ({dti_band} risk).",
        f"Loan amount risk: {loan_amount_risk}.",
        f"Employment risk: {employment_risk}.",
        f"Income stability score: {income_stability_score:.0f}/100.",
    ]
    factors.extend(f"Anomaly: {reason}" for reason in anomaly_reasons)
    return {"key_decision_factors": factors}
