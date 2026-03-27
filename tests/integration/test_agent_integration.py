from __future__ import annotations

"""
Integration tests for the agent loop.
All xAI API calls are mocked with respx.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import respx
from httpx import Response

from grokcode.agent.agent import Agent, DoneEvent, ErrorEvent, ThinkingEvent, ToolCallEvent, ToolResultEvent
from grokcode.agent.grok_client import GrokClient
from grokcode.agent.tool_registry import ToolRegistry
from grokcode.config.config import AppConfig


API_KEY = "test-agent-key"


def _make_config(**kwargs) -> AppConfig:
    return AppConfig(**kwargs)


def _tool_call_response(tool_name: str, args: dict, call_id: str = "call_001") -> dict:
    """Build a non-streaming chat completions response with a tool call."""
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(args),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 20},
    }


def _text_response(text: str) -> dict:
    """Build a non-streaming chat completions response with text content."""
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 30},
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(config: AppConfig, registry: ToolRegistry) -> tuple[Agent, GrokClient]:
    client = GrokClient(api_key=API_KEY, model="grok-3-mini", max_tokens=256)
    agent = Agent(config=config, tool_registry=registry, grok_client=client)
    return agent, client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@respx.mock
async def test_agent_single_turn_no_tools() -> None:
    """Agent returns DoneEvent immediately when Grok responds with no tool calls."""
    respx.post("https://api.x.ai/v1/chat/completions").mock(
        return_value=Response(200, json=_text_response("Hello from Grok!"))
    )

    config = _make_config()
    registry = ToolRegistry()
    agent, client = _make_agent(config, registry)

    events = []
    async for event in agent.run(task="Say hello", stream=False):
        events.append(event)

    await client.close()

    done_events = [e for e in events if isinstance(e, DoneEvent)]
    assert len(done_events) == 1
    assert done_events[0].text == "Hello from Grok!"


@respx.mock
async def test_agent_tool_call_then_done(tmp_path: Path) -> None:
    """Agent calls read_file tool then produces a final response."""
    test_file = tmp_path / "hello.py"
    test_file.write_text("def hello():\n    return 'world'\n")

    # First call: Grok requests read_file
    # Second call: Grok produces final response
    call_count = 0

    def _side_effect(request, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return Response(
                200,
                json=_tool_call_response("read_file", {"path": str(test_file)}),
            )
        return Response(200, json=_text_response("The file contains a hello function."))

    respx.post("https://api.x.ai/v1/chat/completions").mock(side_effect=_side_effect)

    config = _make_config()
    registry = ToolRegistry()

    from grokcode.tools.fs import read_file, FS_TOOL_SCHEMAS
    registry.register("read_file", read_file, FS_TOOL_SCHEMAS[0])

    agent, client = _make_agent(config, registry)
    events = []
    async for event in agent.run(task=f"Read {test_file}", stream=False):
        events.append(event)

    await client.close()

    tool_calls = [e for e in events if isinstance(e, ToolCallEvent)]
    tool_results = [e for e in events if isinstance(e, ToolResultEvent)]
    done = [e for e in events if isinstance(e, DoneEvent)]

    assert len(tool_calls) == 1
    assert tool_calls[0].tool_name == "read_file"
    assert len(tool_results) == 1
    assert "hello" in tool_results[0].result
    assert len(done) == 1


@respx.mock
async def test_agent_write_file_tool(tmp_path: Path) -> None:
    """Agent writes a new file via write_file tool."""
    output_file = tmp_path / "fib.py"

    fib_content = "def fib(n: int) -> int:\n    if n <= 1:\n        return n\n    return fib(n-1) + fib(n-2)\n"

    call_count = 0

    def _side_effect(request, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return Response(
                200,
                json=_tool_call_response(
                    "write_file",
                    {"path": str(output_file), "content": fib_content},
                ),
            )
        return Response(200, json=_text_response("Created fib.py with fibonacci function."))

    respx.post("https://api.x.ai/v1/chat/completions").mock(side_effect=_side_effect)

    config = _make_config()
    registry = ToolRegistry()

    from grokcode.tools.fs import write_file, FS_TOOL_SCHEMAS

    async def _write(path: str, content: str) -> str:
        return await write_file(path, content, auto_confirm=True)

    registry.register("write_file", _write, FS_TOOL_SCHEMAS[2])

    agent, client = _make_agent(config, registry)
    events = []
    async for event in agent.run(task="Create fib.py", stream=False):
        events.append(event)

    await client.close()

    assert output_file.exists()
    assert "def fib" in output_file.read_text()

    done = [e for e in events if isinstance(e, DoneEvent)]
    assert len(done) == 1


@respx.mock
async def test_agent_unknown_tool_returns_error_result() -> None:
    """Agent gracefully handles an unknown tool call — no crash, error in result."""
    respx.post("https://api.x.ai/v1/chat/completions").mock(
        side_effect=[
            Response(200, json=_tool_call_response("nonexistent_tool", {"arg": "val"})),
            Response(200, json=_text_response("Got an error, stopping.")),
        ]
    )

    config = _make_config()
    registry = ToolRegistry()
    agent, client = _make_agent(config, registry)

    events = []
    async for event in agent.run(task="Call unknown tool", stream=False):
        events.append(event)

    await client.close()

    tool_results = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(tool_results) == 1
    assert "unknown tool" in tool_results[0].result.lower()


@respx.mock
async def test_agent_dry_run_does_not_execute_tools(tmp_path: Path) -> None:
    """In --dry-run mode, tools are announced but not executed."""
    output_file = tmp_path / "dry_run_output.py"

    respx.post("https://api.x.ai/v1/chat/completions").mock(
        side_effect=[
            Response(
                200,
                json=_tool_call_response("write_file", {"path": str(output_file), "content": "pass"}),
            ),
            Response(200, json=_text_response("Would have written the file.")),
        ]
    )

    config = _make_config()
    registry = ToolRegistry()

    from grokcode.tools.fs import write_file, FS_TOOL_SCHEMAS

    async def _write_dry(path: str, content: str) -> str:
        return await write_file(path, content, auto_confirm=True)

    registry.register("write_file", _write_dry, FS_TOOL_SCHEMAS[2])

    agent, client = _make_agent(config, registry)
    events = []
    async for event in agent.run(task="Write a file", dry_run=True, stream=False):
        events.append(event)

    await client.close()

    # File must NOT exist — dry run
    assert not output_file.exists()

    tool_results = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(tool_results) == 1
    assert "dry-run" in tool_results[0].result.lower()


@respx.mock
async def test_agent_system_prompt_includes_team_rules() -> None:
    """Workspace team rules are injected into the system prompt sent to Grok."""
    from grokcode.config.config import WorkspaceConfig

    ws = WorkspaceConfig(
        workspace="test",
        collection_id="",
        team_id="team",
        rules=["Always use type hints", "Use Pydantic v2"],
    )
    config = _make_config(workspace_config=ws)

    captured_body: dict = {}

    def _capture(request, *args, **kwargs):
        captured_body.update(json.loads(request.content))
        return Response(200, json=_text_response("Done."))

    respx.post("https://api.x.ai/v1/chat/completions").mock(side_effect=_capture)

    registry = ToolRegistry()
    agent, client = _make_agent(config, registry)

    async for _ in agent.run(task="Write a function", stream=False):
        pass

    await client.close()

    system_msg = next((m for m in captured_body.get("messages", []) if m["role"] == "system"), None)
    assert system_msg is not None
    assert "Always use type hints" in system_msg["content"]
    assert "Use Pydantic v2" in system_msg["content"]
