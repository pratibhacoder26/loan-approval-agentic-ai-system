"""FastMCP servers backing each domain agent.

Each MCP server exposes a small, focused set of tools that the corresponding
agent uses to fetch contextual data or persist outcomes. The servers are
defined with the FastMCP framework so they can equally be run as standalone
processes (``python -m app.services.mcp_servers.applicant_db``) or invoked
in-process during testing.
"""

from app.services.mcp_servers.applicant_db import applicant_db_server
from app.services.mcp_servers.decision_synthesis import decision_synthesis_server
from app.services.mcp_servers.notification_system import notification_server
from app.services.mcp_servers.risk_rules_db import risk_rules_server

__all__ = [
    "applicant_db_server",
    "risk_rules_server",
    "decision_synthesis_server",
    "notification_server",
]
