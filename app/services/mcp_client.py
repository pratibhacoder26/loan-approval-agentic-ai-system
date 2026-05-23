"""Thin wrapper around the FastMCP Client.

Provides ``call_mcp_tool`` — a single async function that opens a client
session against an in-process FastMCP server, invokes a tool, and returns
the unwrapped structured payload.

Centralising this here lets the agents stay focused on business logic and
keeps the transport details (in-process today, network in production) in
one place.
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import Client, FastMCP

logger = logging.getLogger(__name__)


async def call_mcp_tool(
    server: FastMCP,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> Any:
    """Invoke ``tool_name`` on the supplied FastMCP ``server``.

    Returns whatever the tool returned (typically a ``dict``). Raises on
    transport errors or tool exceptions so callers can surface clear failures
    upstream.
    """
    arguments = arguments or {}
    logger.debug("MCP call: %s.%s args=%s", server.name, tool_name, arguments)

    async with Client(server) as client:
        result = await client.call_tool(tool_name, arguments)
        if getattr(result, "is_error", False):
            raise RuntimeError(
                f"MCP tool '{tool_name}' on '{server.name}' returned an error: {result.content}"
            )
        return result.data
