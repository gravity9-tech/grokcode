from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from grokcode.agent.types import GrokResponse, RawToolCall, ToolCall, TokenUsage

logger = logging.getLogger(__name__)

XAI_BASE_URL = "https://api.x.ai/v1"
RETRY_STATUSES = {429, 500, 502, 503}
RETRY_DELAYS = [0.5, 1.0, 2.0]


class GrokClientError(Exception):
    pass


class GrokClient:
    def __init__(self, api_key: str, model: str = "grok-3-mini", max_tokens: int = 8192) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._client = httpx.AsyncClient(
            base_url=XAI_BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "GrokClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = True,
        **kwargs: Any,
    ) -> AsyncGenerator[GrokResponse, None]:
        """Send a chat request, yielding GrokResponse chunks (streaming) or a single response."""
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            body["tools"] = tools
        body.update(kwargs)

        if stream:
            async for response in self._stream_chat(body):
                yield response
        else:
            response = await self._non_stream_chat(body)
            yield response

    async def _stream_chat(self, body: dict) -> AsyncGenerator[GrokResponse, None]:
        """Stream chat completions via SSE."""
        for attempt, delay in enumerate([0.0] + RETRY_DELAYS):
            if delay:
                await asyncio.sleep(delay)
            try:
                async with self._client.stream("POST", "/chat/completions", json=body) as resp:
                    if resp.status_code in RETRY_STATUSES and attempt < len(RETRY_DELAYS):
                        logger.warning("xAI API returned %s, retrying...", resp.status_code)
                        continue
                    if resp.status_code not in (200, 201):
                        body_text = await resp.aread()
                        raise GrokClientError(
                            f"xAI API error {resp.status_code}: {body_text.decode()}"
                        )

                    # Accumulate tool calls and content across SSE chunks
                    accumulated_content = ""
                    accumulated_tool_calls: dict[int, dict] = {}
                    usage: TokenUsage | None = None

                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        if chunk.get("usage"):
                            u = chunk["usage"]
                            usage = TokenUsage(
                                input_tokens=u.get("prompt_tokens", 0),
                                output_tokens=u.get("completion_tokens", 0),
                            )

                        choices = chunk.get("choices", [])
                        if not choices:
                            continue

                        delta = choices[0].get("delta", {})
                        finish_reason = choices[0].get("finish_reason")

                        # Accumulate text content
                        if delta.get("content"):
                            accumulated_content += delta["content"]
                            yield GrokResponse(content=delta["content"])

                        # Accumulate tool calls
                        for tc_delta in delta.get("tool_calls", []):
                            idx = tc_delta.get("index", 0)
                            if idx not in accumulated_tool_calls:
                                accumulated_tool_calls[idx] = {
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            tc = accumulated_tool_calls[idx]
                            if tc_delta.get("id"):
                                tc["id"] = tc_delta["id"]
                            fn = tc_delta.get("function", {})
                            if fn.get("name"):
                                tc["function"]["name"] += fn["name"]
                            if fn.get("arguments"):
                                tc["function"]["arguments"] += fn["arguments"]

                        if finish_reason in ("tool_calls", "stop") and accumulated_tool_calls:
                            tool_calls = _parse_tool_calls(accumulated_tool_calls)
                            yield GrokResponse(
                                content=accumulated_content or None,
                                tool_calls=tool_calls,
                                usage=usage,
                                finish_reason=finish_reason,
                            )
                            accumulated_tool_calls = {}
                            accumulated_content = ""

                    # Final response if there were no tool calls
                    if accumulated_content and not accumulated_tool_calls:
                        yield GrokResponse(
                            content=None,  # content already streamed chunk by chunk
                            tool_calls=[],
                            usage=usage,
                            finish_reason="stop",
                        )
                    return  # success — exit retry loop

            except httpx.TransportError as e:
                if attempt < len(RETRY_DELAYS):
                    logger.warning("Transport error: %s, retrying...", e)
                    continue
                raise GrokClientError(f"Network error after retries: {e}") from e

    async def _non_stream_chat(self, body: dict) -> GrokResponse:
        """Non-streaming chat completions."""
        body = {**body, "stream": False}
        for attempt, delay in enumerate([0.0] + RETRY_DELAYS):
            if delay:
                await asyncio.sleep(delay)
            try:
                resp = await self._client.post("/chat/completions", json=body)
                if resp.status_code in RETRY_STATUSES and attempt < len(RETRY_DELAYS):
                    continue
                resp.raise_for_status()
                data = resp.json()

                choice = data["choices"][0]
                message = choice["message"]
                usage_data = data.get("usage", {})
                usage = TokenUsage(
                    input_tokens=usage_data.get("prompt_tokens", 0),
                    output_tokens=usage_data.get("completion_tokens", 0),
                )

                raw_tool_calls = message.get("tool_calls") or []
                tool_calls = [
                    ToolCall(
                        id=tc["id"],
                        name=tc["function"]["name"],
                        arguments=json.loads(tc["function"]["arguments"]),
                    )
                    for tc in raw_tool_calls
                ]

                return GrokResponse(
                    content=message.get("content"),
                    tool_calls=tool_calls,
                    usage=usage,
                    finish_reason=choice.get("finish_reason"),
                )
            except httpx.HTTPStatusError as e:
                if attempt < len(RETRY_DELAYS):
                    continue
                raise GrokClientError(f"API error: {e}") from e

        raise GrokClientError("Failed after retries")


def _parse_tool_calls(accumulated: dict[int, dict]) -> list[ToolCall]:
    """Convert accumulated SSE tool call fragments into parsed ToolCall objects."""
    tool_calls = []
    for tc in accumulated.values():
        try:
            raw = RawToolCall(**tc)
            args = json.loads(raw.function.arguments) if raw.function.arguments else {}
            tool_calls.append(ToolCall(id=raw.id, name=raw.function.name, arguments=args))
        except Exception as e:
            logger.warning("Failed to parse tool call: %s — %s", tc, e)
    return tool_calls
