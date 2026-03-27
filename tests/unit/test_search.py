from __future__ import annotations

import pytest
import respx
from httpx import Response

from grokcode.search.search import SearchResult, format_results_as_tool_output, web_search, x_search

API_KEY = "test-key"


@respx.mock
async def test_web_search_plain_text_response() -> None:
    """web_search returns a SearchResult from a plain-text API response."""
    respx.post("https://api.x.ai/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "FastAPI docs are at https://fastapi.tiangolo.com. It is a modern Python web framework.",
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
        )
    )

    results = await web_search(query="FastAPI docs", api_key=API_KEY)
    assert len(results) == 1
    assert "FastAPI" in results[0].snippet
    assert results[0].source == "Web"


@respx.mock
async def test_x_search_plain_text_response() -> None:
    """x_search returns a SearchResult with source='X'."""
    respx.post("https://api.x.ai/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "People on X are talking about the new Pydantic v3 release.",
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
        )
    )

    results = await x_search(query="Pydantic v3", api_key=API_KEY)
    assert len(results) >= 1
    assert results[0].source == "X"


@respx.mock
async def test_web_search_annotated_response() -> None:
    """web_search correctly parses url_citation annotations."""
    respx.post("https://api.x.ai/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "FastAPI is great.",
                                    "annotations": [
                                        {
                                            "type": "url_citation",
                                            "title": "FastAPI Docs",
                                            "url": "https://fastapi.tiangolo.com",
                                            "text": "FastAPI is a modern framework.",
                                        }
                                    ],
                                }
                            ],
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
        )
    )

    results = await web_search(query="FastAPI", api_key=API_KEY)
    assert len(results) == 1
    assert results[0].url == "https://fastapi.tiangolo.com"
    assert results[0].title == "FastAPI Docs"


@respx.mock
async def test_search_api_error_raises() -> None:
    respx.post("https://api.x.ai/v1/chat/completions").mock(
        return_value=Response(500, text="Internal Server Error")
    )
    with pytest.raises(RuntimeError, match="Search API error"):
        await web_search(query="test", api_key=API_KEY)


def test_format_results_as_tool_output_empty() -> None:
    assert format_results_as_tool_output([]) == "No results found."


def test_format_results_as_tool_output() -> None:
    results = [
        SearchResult(
            title="FastAPI Docs",
            url="https://fastapi.tiangolo.com",
            snippet="A modern web framework.",
            source="Web",
        )
    ]
    output = format_results_as_tool_output(results)
    assert "FastAPI Docs" in output
    assert "fastapi.tiangolo.com" in output
    assert "modern web framework" in output
