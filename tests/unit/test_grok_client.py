from __future__ import annotations

import json

import pytest
import respx
from httpx import Response

from grokcode.agent.grok_client import GrokClient, GrokClientError
from grokcode.agent.types import TokenUsage


@pytest.fixture
def client() -> GrokClient:
    return GrokClient(api_key="test-key", model="grok-3-mini", max_tokens=256)


@respx.mock
async def test_non_stream_simple_response(client: GrokClient) -> None:
    """Non-streaming chat returns a GrokResponse with content."""
    respx.post("https://api.x.ai/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "Hello, world!"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )
    )

    messages = [{"role": "user", "content": "Say hello"}]
    responses = []
    async for chunk in client.chat(messages, stream=False):
        responses.append(chunk)

    assert len(responses) == 1
    assert responses[0].content == "Hello, world!"
    assert responses[0].usage == TokenUsage(input_tokens=10, output_tokens=5)


@respx.mock
async def test_non_stream_tool_call(client: GrokClient) -> None:
    """Non-streaming response with a tool call is parsed correctly."""
    respx.post("https://api.x.ai/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_abc",
                                    "type": "function",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": '{"path": "main.py"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            },
        )
    )

    messages = [{"role": "user", "content": "Read main.py"}]
    responses = []
    async for chunk in client.chat(messages, stream=False):
        responses.append(chunk)

    assert len(responses) == 1
    assert len(responses[0].tool_calls) == 1
    tc = responses[0].tool_calls[0]
    assert tc.name == "read_file"
    assert tc.arguments == {"path": "main.py"}


@respx.mock
async def test_api_error_raises_client_error(client: GrokClient) -> None:
    """4xx/5xx non-retryable errors raise GrokClientError."""
    respx.post("https://api.x.ai/v1/chat/completions").mock(
        return_value=Response(401, json={"error": "Unauthorized"})
    )

    messages = [{"role": "user", "content": "hello"}]
    with pytest.raises(GrokClientError):
        async for _ in client.chat(messages, stream=False):
            pass


async def test_client_close(client: GrokClient) -> None:
    """Client can be closed without error."""
    await client.close()
