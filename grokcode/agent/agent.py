from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Literal

from pydantic import BaseModel

from grokcode.agent.grok_client import GrokClient
from grokcode.agent.system_prompt import build_system_prompt
from grokcode.agent.tool_registry import ToolRegistry
from grokcode.agent.types import Message, TokenUsage
from grokcode.config.config import AppConfig

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 25


# ---------------------------------------------------------------------------
# Agent event types (discriminated union)
# ---------------------------------------------------------------------------


class ThinkingEvent(BaseModel):
    type: Literal["thinking"] = "thinking"
    text: str


class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool_call_id: str
    tool_name: str
    arguments: dict


class ToolResultEvent(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_name: str
    result: str
    files_touched: list[str] = []


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    text: str | None = None
    usage: TokenUsage | None = None


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


AgentEvent = ThinkingEvent | ToolCallEvent | ToolResultEvent | DoneEvent | ErrorEvent


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class Agent:
    def __init__(
        self,
        config: AppConfig,
        tool_registry: ToolRegistry,
        grok_client: GrokClient,
    ) -> None:
        self.config = config
        self.registry = tool_registry
        self.client = grok_client
        self.message_history: list[Message] = []

    async def run(
        self,
        task: str,
        history: list[dict] | None = None,
        auto_confirm: bool = False,
        dry_run: bool = False,
        stream: bool = True,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Run the agentic loop, yielding events."""
        # Resolve git branch for system prompt
        git_branch = await _get_git_branch()
        system_prompt = build_system_prompt(self.config, git_branch=git_branch)

        # Build initial message list
        messages: list[dict] = [{"role": "system", "content": system_prompt}]

        if history:
            messages.extend(history)

        # Inject workspace context if available
        if self.config.workspace_config and self.config.workspace_config.collection_id:
            workspace_context = await _fetch_workspace_context(
                self.config.workspace_config.collection_id,
                task,
                self.client,
            )
            if workspace_context:
                # Append to system message
                messages[0]["content"] += f"\n\n{workspace_context}"

        messages.append({"role": "user", "content": task})

        tools = self.registry.get_schemas()
        total_usage = TokenUsage(input_tokens=0, output_tokens=0)

        for iteration in range(MAX_ITERATIONS):
            logger.debug("Agent iteration %d/%d", iteration + 1, MAX_ITERATIONS)

            # Accumulate the full response from streaming
            accumulated_content = ""
            accumulated_tool_calls = []

            try:
                async for chunk in self.client.chat(messages, tools=tools, stream=stream):
                    if chunk.content:
                        accumulated_content += chunk.content
                        yield ThinkingEvent(text=chunk.content)
                    if chunk.tool_calls:
                        accumulated_tool_calls = chunk.tool_calls
                    if chunk.usage:
                        total_usage = TokenUsage(
                            input_tokens=total_usage.input_tokens + chunk.usage.input_tokens,
                            output_tokens=total_usage.output_tokens + chunk.usage.output_tokens,
                        )

            except Exception as exc:
                yield ErrorEvent(message=f"API error: {exc}")
                return

            # Build assistant message for history
            assistant_msg: dict = {"role": "assistant"}
            if accumulated_content:
                assistant_msg["content"] = accumulated_content
            if accumulated_tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in accumulated_tool_calls
                ]

            messages.append(assistant_msg)

            # No tool calls → we're done
            if not accumulated_tool_calls:
                self.message_history = [Message(**m) for m in messages[1:]]  # skip system
                yield DoneEvent(text=accumulated_content or None, usage=total_usage)
                return

            # Execute each tool call
            for tool_call in accumulated_tool_calls:
                yield ToolCallEvent(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    arguments=tool_call.arguments,
                )

                if dry_run:
                    result_content = f"[dry-run] Would call {tool_call.name}({tool_call.arguments})"
                else:
                    tool_result = await self.registry.execute(tool_call.name, tool_call.arguments)
                    result_content = tool_result.content

                files_touched = _extract_file_paths(tool_call.name, tool_call.arguments)
                yield ToolResultEvent(
                    tool_name=tool_call.name,
                    result=result_content,
                    files_touched=files_touched,
                )

                # Append tool result message
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_content,
                    }
                )

        # Exhausted max iterations
        self.message_history = [Message(**m) for m in messages[1:]]
        yield ErrorEvent(
            message=f"Max iterations ({MAX_ITERATIONS}) reached without completing task."
        )


async def _get_git_branch() -> str | None:
    """Get the current git branch name, or None if not in a repo."""
    try:
        import asyncio

        proc = await asyncio.create_subprocess_shell(
            "git rev-parse --abbrev-ref HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            return stdout.decode().strip()
    except Exception:
        pass
    return None


async def _fetch_workspace_context(
    collection_id: str,
    task: str,
    client: GrokClient,
) -> str | None:
    """Query the local workspace collection and format results for injection into system prompt."""
    try:
        from grokcode.workspace.collections_client import CollectionsClient

        async with CollectionsClient() as coll_client:
            results = await coll_client.query_collection(
                collection_id=collection_id,
                query=task,
                top_k=5,
            )

        if not results:
            return None

        lines = ["<workspace_context>"]
        for r in results:
            source = r.metadata.get("path", r.doc_id or "workspace")
            lines.append(f"[Source: {source}]")
            lines.append(r.content[:800])
            lines.append("")
        lines.append("</workspace_context>")
        return "\n".join(lines)

    except Exception as e:
        logger.warning("Failed to fetch workspace context: %s", e)
        return None


def _extract_file_paths(tool_name: str, args: dict) -> list[str]:
    """Extract file paths from tool arguments for session tracking."""
    file_tools = {"read_file", "write_file", "edit_file", "delete_file"}
    if tool_name in file_tools and "path" in args:
        return [args["path"]]
    return []
