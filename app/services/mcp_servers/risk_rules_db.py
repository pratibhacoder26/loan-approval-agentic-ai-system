"""RiskRulesDB MCP server.

Provides quantitative risk calculations and rule-based assessments used by the
Financial Risk Analysis Agent: DTI, credit-score banding, loan-amount risk,
and anomaly detection.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from app.constants import (
    CREDIT_SCORE_EXCELLENT,
    CREDIT_SCORE_FAIR,
    CREDIT_SCORE_GOOD,
    CREDIT_SCORE_POOR,
    DTI_HIGH,
    DTI_LOW,
    DTI_MEDIUM,
    LOAN_AMOUNT_HIGH,
    LOAN_AMOUNT_LOW,
    LOAN_AMOUNT_MEDIUM,
    MCPServerName,
    RiskLevel,
)

risk_rules_server = FastMCP(name=MCPServerName.RISK_RULES_DB.value)


@risk_rules_server.tool
def compute_debt_to_income(
    income: float,
    existing_liabilities: float,
    loan_amount: float,
    loan_tenure_months: int,
) -> dict[str, Any]:
    """Compute monthly debt-to-income (DTI) ratio and risk band.

    Approximates the new loan's monthly EMI using a 12% annualised rate and
    standard amortisation. Existing liabilities are assumed to already be
    expressed as an annualised obligation.
    """
    annual_rate = 0.12
    monthly_rate = annual_rate / 12.0
    n = max(1, loan_tenure_months)

    if monthly_rate == 0:
        emi = loan_amount / n
    else:
        emi = (
            loan_amount
            * monthly_rate
            * (1 + monthly_rate) ** n
            / ((1 + monthly_rate) ** n - 1)
        )

    monthly_income = max(1.0, income / 12.0)
    monthly_existing = existing_liabilities / 12.0
    dti = (emi + monthly_existing) / monthly_income

    if dti <= DTI_LOW:
        band = RiskLevel.LOW
    elif dti <= DTI_MEDIUM:
        band = RiskLevel.MEDIUM
    elif dti <= DTI_HIGH:
        band = RiskLevel.HIGH
    else:
        band = RiskLevel.CRITICAL

    return {
        "estimated_monthly_emi": round(emi, 2),
        "monthly_income": round(monthly_income, 2),
        "monthly_existing_obligations": round(monthly_existing, 2),
        "debt_to_income_ratio": round(dti, 4),
        "dti_risk_band": band.value,
    }


@risk_rules_server.tool
def classify_credit_score(credit_score: int) -> dict[str, Any]:
    """Map a credit score to a risk band and short rationale."""
    if credit_score >= CREDIT_SCORE_EXCELLENT:
        risk = RiskLevel.LOW
        rationale = "Excellent credit score — strong repayment history indicators."
    elif credit_score >= CREDIT_SCORE_GOOD:
        risk = RiskLevel.LOW
        rationale = "Good credit score — generally reliable borrower profile."
    elif credit_score >= CREDIT_SCORE_FAIR:
        risk = RiskLevel.MEDIUM
        rationale = "Fair credit score — acceptable but requires closer review."
    elif credit_score >= CREDIT_SCORE_POOR:
        risk = RiskLevel.HIGH
        rationale = "Poor credit score — elevated default probability."
    else:
        risk = RiskLevel.CRITICAL
        rationale = "Very poor credit score — significant repayment concern."

    return {
        "credit_score": credit_score,
        "credit_score_risk_level": risk.value,
        "rationale": rationale,
    }


@risk_rules_server.tool
def classify_loan_amount(loan_amount: float, income: float) -> dict[str, Any]:
    """Risk-band a loan amount against absolute scale and income multiple."""
    if loan_amount <= LOAN_AMOUNT_LOW:
        absolute_band = RiskLevel.LOW
    elif loan_amount <= LOAN_AMOUNT_MEDIUM:
        absolute_band = RiskLevel.MEDIUM
    elif loan_amount <= LOAN_AMOUNT_HIGH:
        absolute_band = RiskLevel.HIGH
    else:
        absolute_band = RiskLevel.CRITICAL

    income_multiple = loan_amount / max(1.0, income)
    if income_multiple <= 3:
        ratio_band = RiskLevel.LOW
    elif income_multiple <= 6:
        ratio_band = RiskLevel.MEDIUM
    elif income_multiple <= 10:
        ratio_band = RiskLevel.HIGH
    else:
        ratio_band = RiskLevel.CRITICAL

    # Combine: take the worst of the two.
    severity = {
        RiskLevel.LOW: 0,
        RiskLevel.MEDIUM: 1,
        RiskLevel.HIGH: 2,
        RiskLevel.CRITICAL: 3,
    }
    worst = max(absolute_band, ratio_band, key=lambda b: severity[b])

    return {
        "loan_amount": loan_amount,
        "income_multiple": round(income_multiple, 2),
        "absolute_band": absolute_band.value,
        "income_ratio_band": ratio_band.value,
        "loan_amount_risk": worst.value,
    }


@risk_rules_server.tool
def detect_anomalies(application: dict[str, Any]) -> dict[str, Any]:
    """Surface inconsistencies that may indicate fraud or data-entry errors."""
    anomalies: list[str] = []
    income = float(application.get("income") or 0)
    loan_amount = float(application.get("loan_amount") or 0)
    credit_score = int(application.get("credit_score") or 0)
    existing_liabilities = float(application.get("existing_liabilities") or 0)
    age = int(application.get("age") or 0)

    if income > 0 and existing_liabilities / income > 1.5:
        anomalies.append("Existing liabilities exceed 150% of annual income.")
    if income > 0 and loan_amount / income > 15:
        anomalies.append("Requested loan exceeds 15× annual income.")
    if credit_score >= CREDIT_SCORE_EXCELLENT and existing_liabilities > income * 1.2:
        anomalies.append(
            "High credit score paired with very high existing liabilities — verify bureau report."
        )
    if age < 21 and loan_amount > 500_000:
        anomalies.append("Young applicant with disproportionately large loan request.")
    if age > 60 and application.get("loan_tenure_months", 0) > 240:
        anomalies.append("Long tenure relative to applicant age — repayment horizon concern.")

    return {
        "anomaly_detected": bool(anomalies),
        "anomaly_reasons": anomalies,
    }


@risk_rules_server.tool
def composite_risk_score(
    dti_band: str,
    credit_band: str,
    loan_amount_band: str,
    employment_risk: str,
    anomaly_detected: bool,
) -> dict[str, Any]:
    """Combine individual signals into a single 0-100 risk score.

    Higher means riskier. The Loan Decision Agent uses this together with
    business thresholds (defined in constants) to route the application.
    """
    weights = {
        RiskLevel.LOW.value: 0,
        RiskLevel.MEDIUM.value: 30,
        RiskLevel.HIGH.value: 65,
        RiskLevel.CRITICAL.value: 95,
    }
    factors = [
        weights.get(dti_band, 50) * 0.35,
        weights.get(credit_band, 50) * 0.30,
        weights.get(loan_amount_band, 50) * 0.20,
        weights.get(employment_risk, 50) * 0.15,
    ]
    score = sum(factors)
    if anomaly_detected:
        score = min(100.0, score + 15.0)
    return {"composite_risk_score": round(score, 2)}
