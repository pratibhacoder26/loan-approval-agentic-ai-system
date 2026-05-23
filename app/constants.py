"""System-wide constants and enums for the Loan Approval System."""

from __future__ import annotations

from enum import Enum


class LoanDecision(str, Enum):
    """Final classification of a loan application."""

    APPROVED = "Approved"
    REJECTED = "Rejected"
    MANUAL_REVIEW = "Requires Manual Review"


class EmploymentType(str, Enum):
    """Supported employment categories."""

    SALARIED = "Salaried"
    SELF_EMPLOYED = "Self-Employed"
    BUSINESS_OWNER = "Business Owner"
    CONTRACT = "Contract"
    UNEMPLOYED = "Unemployed"
    RETIRED = "Retired"


class RiskLevel(str, Enum):
    """Generic risk band used across agents."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class AgentName(str, Enum):
    """Identifiers for the four domain agents."""

    APPLICANT_PROFILE = "ApplicantProfileAgent"
    FINANCIAL_RISK = "FinancialRiskAnalysisAgent"
    LOAN_DECISION = "LoanDecisionAgent"
    COMPLIANCE = "ComplianceActionAgent"


class MCPServerName(str, Enum):
    """Logical names of the MCP servers backing each agent."""

    APPLICANT_DB = "ApplicantDB"
    RISK_RULES_DB = "RiskRulesDB"
    DECISION_SYNTHESIS = "DecisionSynthesis"
    NOTIFICATION_SYSTEM = "NotificationSystem"


# --- Risk / decision thresholds ----------------------------------------------

CREDIT_SCORE_EXCELLENT = 750
CREDIT_SCORE_GOOD = 700
CREDIT_SCORE_FAIR = 650
CREDIT_SCORE_POOR = 600

DTI_LOW = 0.30
DTI_MEDIUM = 0.45
DTI_HIGH = 0.60

# Composite risk score (0-100) decision bands
RISK_APPROVE_MAX = 35
RISK_REVIEW_MAX = 65

# Loan amount risk bands (in INR equivalent units)
LOAN_AMOUNT_LOW = 500_000
LOAN_AMOUNT_MEDIUM = 2_000_000
LOAN_AMOUNT_HIGH = 5_000_000

MIN_APPLICANT_AGE = 21
MAX_APPLICANT_AGE = 65

DEFAULT_LOAN_TENURE_MIN_MONTHS = 12
DEFAULT_LOAN_TENURE_MAX_MONTHS = 360
