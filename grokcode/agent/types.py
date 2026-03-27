from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list | None = None
    tool_call_id: str | None = None
    tool_calls: list[RawToolCall] | None = None


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict


class RawToolCall(BaseModel):
    """Raw tool call as returned by the xAI API."""

    id: str
    type: str = "function"
    function: ToolCallFunction


class ToolCallFunction(BaseModel):
    name: str
    arguments: str  # JSON string — always json.loads() before use


class ToolCall(BaseModel):
    """Parsed tool call with deserialized arguments."""

    id: str
    name: str
    arguments: dict


class ToolResult(BaseModel):
    tool_call_id: str
    content: str


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int


class GrokResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = []
    usage: TokenUsage | None = None
    finish_reason: str | None = None
