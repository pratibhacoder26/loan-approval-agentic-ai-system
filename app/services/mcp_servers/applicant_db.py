"""ApplicantDB MCP server.

Provides tools the Applicant Profile Agent uses to retrieve historical
applicant context: prior applications, KYC status, employment history, and
credit bureau summaries. In a production deployment these would back onto a
real data store; here we simulate deterministic responses keyed by applicant
attributes so the system is fully self-contained.
"""

from __future__ import annotations

import hashlib
from typing import Any

from fastmcp import FastMCP

from app.constants import (
    CREDIT_SCORE_EXCELLENT,
    CREDIT_SCORE_FAIR,
    CREDIT_SCORE_GOOD,
    CREDIT_SCORE_POOR,
    EmploymentType,
    MCPServerName,
    RiskLevel,
)

applicant_db_server = FastMCP(name=MCPServerName.APPLICANT_DB.value)


def _stable_int(seed: str, modulus: int) -> int:
    """Return a deterministic integer derived from an input seed."""
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulus


@applicant_db_server.tool
def fetch_kyc_status(applicant_id: str) -> dict[str, Any]:
    """Return the KYC verification status for an applicant.

    In production this would call the bank's identity verification service.
    """
    verified = _stable_int(f"kyc::{applicant_id}", 100) > 5  # 95% verified
    return {
        "applicant_id": applicant_id,
        "kyc_verified": verified,
        "id_document_on_file": verified,
        "address_proof_on_file": verified,
        "last_verified_days_ago": _stable_int(f"kyc-age::{applicant_id}", 365),
    }


@applicant_db_server.tool
def fetch_employment_history(
    applicant_id: str,
    employment_type: str,
) -> dict[str, Any]:
    """Return employment tenure information for the applicant."""
    months = _stable_int(f"emp::{applicant_id}", 240) + 6  # 6-246 months
    risk_map = {
        EmploymentType.SALARIED.value: RiskLevel.LOW,
        EmploymentType.RETIRED.value: RiskLevel.LOW,
        EmploymentType.BUSINESS_OWNER.value: RiskLevel.MEDIUM,
        EmploymentType.SELF_EMPLOYED.value: RiskLevel.MEDIUM,
        EmploymentType.CONTRACT.value: RiskLevel.HIGH,
        EmploymentType.UNEMPLOYED.value: RiskLevel.CRITICAL,
    }
    employment_risk = risk_map.get(employment_type, RiskLevel.MEDIUM).value

    # Short tenure escalates risk one band (except CRITICAL which stays).
    if months < 12 and employment_risk == RiskLevel.LOW.value:
        employment_risk = RiskLevel.MEDIUM.value
    elif months < 12 and employment_risk == RiskLevel.MEDIUM.value:
        employment_risk = RiskLevel.HIGH.value

    return {
        "applicant_id": applicant_id,
        "employment_type": employment_type,
        "tenure_months": months,
        "employment_risk": employment_risk,
    }


@applicant_db_server.tool
def fetch_credit_history(applicant_id: str, credit_score: int) -> dict[str, Any]:
    """Summarise the applicant's credit bureau record."""
    if credit_score >= CREDIT_SCORE_EXCELLENT:
        band = "Excellent"
    elif credit_score >= CREDIT_SCORE_GOOD:
        band = "Good"
    elif credit_score >= CREDIT_SCORE_FAIR:
        band = "Fair"
    elif credit_score >= CREDIT_SCORE_POOR:
        band = "Poor"
    else:
        band = "Very Poor"

    delinquencies_24m = _stable_int(f"del::{applicant_id}", 5)
    open_accounts = _stable_int(f"acc::{applicant_id}", 7) + 1
    utilisation = round(_stable_int(f"util::{applicant_id}", 100) / 100.0, 2)

    summary = (
        f"Credit score {credit_score} ({band}). "
        f"{open_accounts} open accounts, {delinquencies_24m} delinquencies in last 24 months, "
        f"revolving utilisation {int(utilisation * 100)}%."
    )

    return {
        "applicant_id": applicant_id,
        "credit_score": credit_score,
        "credit_band": band,
        "open_accounts": open_accounts,
        "delinquencies_24m": delinquencies_24m,
        "utilisation": utilisation,
        "summary": summary,
    }


@applicant_db_server.tool
def fetch_income_stability(
    applicant_id: str,
    income: float,
    employment_type: str,
) -> dict[str, Any]:
    """Compute an income stability score in [0, 100]."""
    # Salaried + higher income trends to a higher stability score.
    base = {
        EmploymentType.SALARIED.value: 80.0,
        EmploymentType.RETIRED.value: 70.0,
        EmploymentType.BUSINESS_OWNER.value: 60.0,
        EmploymentType.SELF_EMPLOYED.value: 55.0,
        EmploymentType.CONTRACT.value: 45.0,
        EmploymentType.UNEMPLOYED.value: 10.0,
    }.get(employment_type, 50.0)

    # Income bump (log-ish): larger incomes give modest extra stability.
    income_bonus = min(15.0, (income / 100_000.0) * 1.5)
    jitter = (_stable_int(f"inc::{applicant_id}", 11) - 5)  # -5..+5
    score = max(0.0, min(100.0, base + income_bonus + jitter))

    return {
        "applicant_id": applicant_id,
        "income_stability_score": round(score, 2),
        "monthly_income_estimate": round(income / 12.0, 2),
    }


@applicant_db_server.tool
def check_application_completeness(application: dict[str, Any]) -> dict[str, Any]:
    """Flag missing or inconsistent fields in the submitted application."""
    required = [
        "full_name",
        "age",
        "income",
        "employment_type",
        "credit_score",
        "loan_amount",
        "loan_tenure_months",
        "location",
    ]
    flags: list[str] = []
    for field in required:
        if application.get(field) in (None, "", 0):
            # 0 is acceptable for existing_liabilities only — not in `required`.
            flags.append(f"missing:{field}")

    if not application.get("purpose"):
        flags.append("warning:loan_purpose_not_provided")

    return {
        "complete": not any(f.startswith("missing:") for f in flags),
        "flags": flags,
    }
