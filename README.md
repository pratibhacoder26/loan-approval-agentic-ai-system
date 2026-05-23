# Intelligent Loan Approval System — Agentic AI

Multi-agent loan-approval pipeline implementing the case study in
[claude.md](claude.md). Submits a loan application through a chain of
domain agents (Profile → Risk → Decision → Compliance) orchestrated by
LangGraph and powered by Anthropic Claude Sonnet 4.6.

# Assumptions: 
* All financial figures in the system are expressed in Indian Rupees (INR). 
* Applicants are residents of India, aged 18–65, and employed as salaried, self-employed, or business owners. 
* Credit history is obtained from recognized Indian bureaus, with scores ranging from 300–900. 
* Supported loan types include personal, home, and car loans, with maximum tenures of 5 years for personal/car loans and 30 years for home loans. 
* Applicants report all existing liabilities, and income is verified via official documents. 
* The system considers regional economic and regulatory variations for risk assessment. 
* Loan decisions are categorized as Approved, Rejected, or Requires Manual Review, with LLM explanations used solely for audit and transparency purposes. 
* All operations comply with RBI guidelines, timestamps are in IST (UTC+5:30), and sensitive data is encrypted. 
* Agents communicate reliably through MCP servers, and LLM outputs supplement agent reasoning without overriding deterministic decision logic.

## Architecture

```
┌──────────────────┐    ┌─────────────────┐    ┌─────────────────────────────┐
│  Streamlit UI    │───▶│ FastAPI Service │───▶│  LangGraph Orchestrator     │
└──────────────────┘    └─────────────────┘    │  ┌───────────────────────┐  │
                                               │  │ Applicant Profile     │  │
                                               │  │ Financial Risk        │  │
                                               │  │ Loan Decision         │  │
                                               │  │ Compliance / Action   │  │
                                               │  └─────────┬─────────────┘  │
                                               └────────────┼────────────────┘
                                                            ▼
                                               ┌─────────────────────────────┐
                                               │ FastMCP Servers             │
                                               │  • ApplicantDB              │
                                               │  • RiskRulesDB              │
                                               │  • DecisionSynthesis        │
                                               │  • NotificationSystem       │
                                               └─────────────────────────────┘
                                                            ▲
                                                            │
                                               ┌─────────────────────────────┐
                                               │ Claude Sonnet 4.6 (LLM)     │
                                               └─────────────────────────────┘
```

## Project layout

```
app/
├── api/                    FastAPI router (REST endpoints)
├── agents/                 Four domain agents
├── orchestration/          LangGraph workflow + state
├── services/
│   ├── llm_service.py      Anthropic async client
│   ├── mcp_client.py       FastMCP in-process client helper
│   └── mcp_servers/        Four MCP servers
├── ui/                     Streamlit chatbot
├── config.py               Pydantic Settings (env-driven)
├── constants.py            Enums + thresholds
├── models.py               Pydantic models exchanged across the system
└── main.py                 FastAPI app factory
scripts/
├── run_api.sh              Launch FastAPI service
└── run_ui.sh               Launch Streamlit UI
```

## Setup

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Configure environment in `.env`:

```dotenv
ANTHROPIC_API_KEY="sk-ant-..."
MODEL_NAME="claude-sonnet-4-6"
# Optional overrides
API_HOST=0.0.0.0
API_PORT=8000
UI_PORT=8501
API_BASE_URL=http://localhost:8000
```

## Running

In two terminals:

```bash
# Terminal 1 — backend
./scripts/run_api.sh

# Terminal 2 — UI
./scripts/run_ui.sh
```

UI: <http://localhost:8501> · API docs: <http://localhost:8000/docs>

## REST API

`POST /api/v1/loan/evaluate`

```json
{
  "full_name": "Asha Patel",
  "age": 34,
  "income": 950000,
  "employment_type": "Salaried",
  "credit_score": 735,
  "loan_amount": 1500000,
  "loan_tenure_months": 60,
  "existing_liabilities": 120000,
  "location": "Bengaluru, IN",
  "purpose": "Home renovation"
}
```

Response envelope (`ApiSuccess`) includes:

- `applicant_profile` — Profile agent output
- `financial_risk` — Risk agent output (LLM-authored rationale)
- `loan_decision` — Final classification, risk score, confidence, factors, explanation
- `compliance_action` — Case id, action taken, notification status
- `agent_trace` — Per-agent latency trace

## Agents

| Agent | MCP Server | Key Outputs |
| --- | --- | --- |
| Applicant Profile | ApplicantDB | Income stability, employment risk, credit history, completeness flags |
| Financial Risk Analysis | RiskRulesDB | DTI, credit risk, loan-amount risk, anomalies, composite score, LLM reasoning |
| Loan Decision | DecisionSynthesis | Classification, risk score, confidence, key factors, applicant-facing explanation |
| Compliance & Action | NotificationSystem | Case id, action taken, notification dispatch, audit summary |

## Tech stack

- **UI:** Streamlit
- **Microservice:** FastAPI + Uvicorn
- **Orchestration:** LangGraph + LangChain
- **Agents:** Async Python classes invoking FastMCP tools
- **MCP framework:** FastMCP
- **LLM:** Anthropic Claude Sonnet 4.6 (`anthropic` SDK)
- **Agent SDK:** `claude-agent-sdk`
- **Python:** 3.12
