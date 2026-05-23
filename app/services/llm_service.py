"""Anthropic LLM client wrapper used by the agents.

Centralises prompt invocation against Claude Sonnet 4.6 (configurable via
``MODEL_NAME``). Returns clean strings and offers a JSON-mode helper for
agents that need structured output from the model.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from anthropic import APIError, AsyncAnthropic

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMService:
    """Anthropic async client with sensible defaults for this system."""

    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Run a single-turn completion and return the text body."""
        settings = self._settings
        try:
            response = await self._client.messages.create(
                model=settings.model_name,
                max_tokens=max_tokens or settings.llm_max_tokens,
                temperature=temperature if temperature is not None else settings.llm_temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except APIError as exc:  # pragma: no cover - network path
            logger.exception("Anthropic API error: %s", exc)
            raise

        return "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        ).strip()

    async def complete_json(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Run a completion expected to return strict JSON and parse it.

        Tolerates JSON wrapped in Markdown fences (```json ... ```).
        """
        raw = await self.complete(
            system=system,
            user=user,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return _extract_json(raw)


def _extract_json(text: str) -> dict[str, Any]:
    """Best-effort JSON extraction from model output."""
    candidate = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, re.DOTALL)
    if fence:
        candidate = fence.group(1)
    else:
        # Fall back to the largest balanced JSON object substring.
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if match:
            candidate = match.group(0)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse JSON from LLM output: %s\n---\n%s", exc, text)
        raise


# Module-level singleton.
_service: LLMService | None = None
_lock = asyncio.Lock()


async def get_llm_service() -> LLMService:
    """Lazily build and return the shared LLM service."""
    global _service
    if _service is None:
        async with _lock:
            if _service is None:
                _service = LLMService()
    return _service
