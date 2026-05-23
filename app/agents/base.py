"""Shared base class for the four domain agents."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from app.constants import AgentName

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Common scaffolding for an agent: identity, tracing, and run hook."""

    name: AgentName

    def __init__(self, name: AgentName) -> None:
        self.name = name

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent and return a trace-friendly payload."""
        start = time.perf_counter()
        logger.info("[%s] starting", self.name.value)
        try:
            output = await self._run(context)
        except Exception:
            logger.exception("[%s] failed", self.name.value)
            raise
        elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
        logger.info("[%s] completed in %sms", self.name.value, elapsed_ms)
        return {
            "agent": self.name.value,
            "elapsed_ms": elapsed_ms,
            "output": output,
        }

    @abstractmethod
    async def _run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Subclasses implement the agent's actual workflow here."""
        raise NotImplementedError
