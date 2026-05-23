"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Centralised, validated runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM ------------------------------------------------------------------
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")
    model_name: str = Field("claude-sonnet-4-6", alias="MODEL_NAME")
    llm_max_tokens: int = Field(1024, alias="LLM_MAX_TOKENS")
    llm_temperature: float = Field(0.0, alias="LLM_TEMPERATURE")

    # --- FastAPI microservice -------------------------------------------------
    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8000, alias="API_PORT")
    api_log_level: str = Field("info", alias="API_LOG_LEVEL")

    # --- Streamlit UI ---------------------------------------------------------
    ui_port: int = Field(8501, alias="UI_PORT")
    api_base_url: str = Field("http://localhost:8000", alias="API_BASE_URL")

    # --- MCP servers (in-process by default) ----------------------------------
    mcp_applicant_db_url: str = Field("inproc://applicant_db", alias="MCP_APPLICANT_DB_URL")
    mcp_risk_rules_url: str = Field("inproc://risk_rules", alias="MCP_RISK_RULES_URL")
    mcp_decision_url: str = Field("inproc://decision_synthesis", alias="MCP_DECISION_URL")
    mcp_notification_url: str = Field("inproc://notification", alias="MCP_NOTIFICATION_URL")

    # --- Behaviour ------------------------------------------------------------
    enable_real_llm: bool = Field(True, alias="ENABLE_REAL_LLM")
    request_timeout_seconds: int = Field(60, alias="REQUEST_TIMEOUT_SECONDS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Cached so all subsystems share identical configuration without re-reading
    the environment on every access.
    """
    # Normalise the model name: the SDK expects dashed form (claude-sonnet-4-6)
    # but operators commonly write the marketing form (claude-sonnet-4.6).
    settings = Settings()  # type: ignore[call-arg]
    if "." in settings.model_name and settings.model_name.startswith("claude-"):
        settings.model_name = settings.model_name.replace(".", "-")
    return settings
