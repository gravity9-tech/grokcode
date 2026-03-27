from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from grokcode.agent.types import ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self, session_id: str = "") -> None:
        self._functions: dict[str, Callable[..., Any]] = {}
        self._schemas: dict[str, dict] = {}
        self._session_id = session_id

    def register(self, name: str, fn: Callable[..., Any], schema: dict) -> None:
        """Register a tool function with its OpenAI-compatible schema."""
        self._functions[name] = fn
        self._schemas[name] = schema

    def get_schemas(self) -> list[dict]:
        """Return all tool schemas in OpenAI format."""
        return list(self._schemas.values())

    async def execute(self, name: str, args: dict) -> ToolResult:
        """Dispatch a tool call by name. Returns ToolResult even on error."""
        fn = self._functions.get(name)
        if fn is None:
            return ToolResult(
                tool_call_id="",
                content=f"Error: unknown tool '{name}'. Available tools: {', '.join(self._functions)}",
            )

        content = ""
        try:
            if inspect.iscoroutinefunction(fn):
                result = await fn(**args)
            else:
                maybe = fn(**args)
                # Handle lambdas that wrap async functions — they return a coroutine
                if inspect.isawaitable(maybe):
                    result = await maybe
                else:
                    result = maybe

            content = str(result) if result is not None else "Done."
            logger.debug("Tool %s(%s) -> %s", name, args, content[:200])

        except Exception as exc:
            content = f"Tool error in '{name}': {type(exc).__name__}: {exc}"
            logger.warning(content)

        # Async audit log (fire-and-forget)
        asyncio.create_task(
            _audit(
                session_id=self._session_id,
                tool=name,
                args_summary=_summarise(args),
                result_summary=content[:200],
            )
        )

        return ToolResult(tool_call_id="", content=content)


async def _audit(
    session_id: str,
    tool: str,
    args_summary: str,
    result_summary: str,
) -> None:
    try:
        from grokcode.utils.audit import AuditEntry, log_action

        await log_action(
            AuditEntry(
                timestamp=datetime.now(),
                session_id=session_id,
                tool=tool,
                args_summary=args_summary,
                result_summary=result_summary,
            )
        )
    except Exception:
        pass  # audit failure must never crash the agent


def _summarise(args: dict) -> str:
    parts = []
    for k, v in args.items():
        s = repr(v)
        if len(s) > 60:
            s = s[:57] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)
