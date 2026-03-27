from __future__ import annotations

"""
Remote MCP (Model Context Protocol) tool client.

Reads mcp_servers from grokcode.workspace.json and makes those tools
available to the agent. Implements the MCP HTTP transport spec:
  GET  <server_url>/tools          → list available tools + schemas
  POST <server_url>/tools/<name>   → call a tool, return string result
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 10.0
CALL_TIMEOUT = 30.0


class McpError(Exception):
    pass


async def discover_tools(server_url: str, api_key: str | None = None) -> list[dict]:
    """
    GET <server_url>/tools — returns a list of OpenAI-compatible tool schemas.
    Falls back to empty list on any error so agent startup never fails.
    """
    headers: dict[str, str] = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=DISCOVERY_TIMEOUT) as client:
            resp = await client.get(f"{server_url.rstrip('/')}/tools", headers=headers)
            if resp.status_code != 200:
                logger.warning("MCP discovery failed for %s: %s", server_url, resp.status_code)
                return []
            data = resp.json()
            tools: list[dict] = data if isinstance(data, list) else data.get("tools", [])
            logger.debug("Discovered %d tools from %s", len(tools), server_url)
            return tools
    except Exception as e:
        logger.warning("MCP discovery error for %s: %s", server_url, e)
        return []


async def call_mcp_tool(
    server_url: str,
    tool_name: str,
    args: dict[str, Any],
    api_key: str | None = None,
) -> str:
    """
    POST <server_url>/tools/<tool_name> — call a remote MCP tool.
    Returns the result as a string.
    """
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    url = f"{server_url.rstrip('/')}/tools/{tool_name}"

    try:
        async with httpx.AsyncClient(timeout=CALL_TIMEOUT) as client:
            resp = await client.post(url, json=args, headers=headers)
            if resp.status_code not in (200, 201):
                raise McpError(
                    f"MCP tool call failed: {resp.status_code} — {resp.text[:300]}"
                )
            data = resp.json()
            # Normalise response: extract content string
            if isinstance(data, str):
                return data
            if isinstance(data, dict):
                return data.get("content") or data.get("result") or str(data)
            return str(data)
    except McpError:
        raise
    except Exception as e:
        raise McpError(f"MCP error calling {tool_name} at {server_url}: {e}") from e


async def register_mcp_servers(
    registry: object,
    mcp_servers: list[object],
) -> int:
    """
    Discover and register tools from all configured MCP servers.
    Returns the count of tools registered.
    """
    from functools import partial
    from grokcode.agent.tool_registry import ToolRegistry
    from grokcode.config.config import McpServer

    reg: ToolRegistry = registry  # type: ignore[assignment]
    count = 0

    for server in mcp_servers:
        srv: McpServer = server  # type: ignore[assignment]
        tools = await discover_tools(server_url=srv.url)

        for schema in tools:
            fn_schema = schema.get("function", schema)
            name = fn_schema.get("name", "")
            if not name:
                continue

            # Create a bound dispatcher for this server + tool
            dispatcher = partial(call_mcp_tool, srv.url, name)

            async def _dispatch(**kwargs: Any) -> str:
                return await dispatcher(args=kwargs)

            reg.register(
                name=f"mcp_{srv.name}_{name}",
                fn=_dispatch,
                schema={
                    "type": "function",
                    "function": {
                        **fn_schema,
                        "name": f"mcp_{srv.name}_{name}",
                        "description": (
                            f"[{srv.name}] {fn_schema.get('description', '')}"
                        ),
                    },
                },
            )
            count += 1
            logger.debug("Registered MCP tool: mcp_%s_%s", srv.name, name)

    return count
