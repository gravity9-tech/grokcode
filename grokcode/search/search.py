from __future__ import annotations

"""
Web search and X (Twitter) search via xAI's native search tools.

xAI exposes search as special tool types in the chat completions API:
  {"type": "web_search"}  — live web search
  {"type": "x_search"}    — X (Twitter) search

We call completions with the appropriate tool enabled and extract
results from the message annotations / content.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

XAI_BASE_URL = "https://api.x.ai/v1"


class SearchResult:
    def __init__(self, title: str, url: str, snippet: str, source: str) -> None:
        self.title = title
        self.url = url
        self.snippet = snippet
        self.source = source

    def to_text(self) -> str:
        return f"[{self.source}] {self.title}\n{self.url}\n{self.snippet}"


async def web_search(query: str, api_key: str, max_results: int = 5) -> list[SearchResult]:
    """Search the web using xAI's web_search tool."""
    return await _search(query=query, api_key=api_key, tool_type="web_search", max_results=max_results)


async def x_search(query: str, api_key: str, max_results: int = 5) -> list[SearchResult]:
    """Search X (Twitter) using xAI's x_search tool."""
    return await _search(query=query, api_key=api_key, tool_type="x_search", max_results=max_results)


async def _search(
    query: str,
    api_key: str,
    tool_type: str,
    max_results: int,
) -> list[SearchResult]:
    source_label = "X" if tool_type == "x_search" else "Web"

    async with httpx.AsyncClient(
        base_url=XAI_BASE_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=httpx.Timeout(30.0),
    ) as client:
        body: dict[str, Any] = {
            "model": "grok-3-mini",
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Search for: {query}\n\n"
                        f"Return a list of the top {max_results} results with title, URL, and a brief summary."
                    ),
                }
            ],
            "tools": [{"type": tool_type}],
        }

        resp = await client.post("/chat/completions", json=body)
        if resp.status_code != 200:
            raise RuntimeError(f"Search API error {resp.status_code}: {resp.text[:300]}")

        data = resp.json()

    results: list[SearchResult] = []
    choices = data.get("choices", [])
    if not choices:
        return results

    message = choices[0].get("message", {})
    content_blocks = message.get("content", "")

    # Handle annotated content (preferred — structured citations)
    if isinstance(content_blocks, list):
        for block in content_blocks:
            if block.get("type") == "text":
                for ann in block.get("annotations", []):
                    if ann.get("type") in ("url_citation", "tweet"):
                        results.append(
                            SearchResult(
                                title=ann.get("title") or ann.get("url", ""),
                                url=ann.get("url", ""),
                                snippet=ann.get("text", ""),
                                source=source_label,
                            )
                        )
        # Include main text as a summary result if no annotations
        if not results:
            text = " ".join(
                b.get("text", "") for b in content_blocks if b.get("type") == "text"
            )
            if text:
                results.append(
                    SearchResult(
                        title=f"{source_label} search: {query}",
                        url="",
                        snippet=text[:500],
                        source=source_label,
                    )
                )
    elif isinstance(content_blocks, str) and content_blocks:
        # Plain text response — parse as summary
        results.append(
            SearchResult(
                title=f"{source_label} search: {query}",
                url="",
                snippet=content_blocks[:1000],
                source=source_label,
            )
        )

    return results[:max_results]


def format_results_as_tool_output(results: list[SearchResult]) -> str:
    """Format search results as a string for agent tool output."""
    if not results:
        return "No results found."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.title}")
        if r.url:
            lines.append(f"   {r.url}")
        lines.append(f"   {r.snippet}")
        lines.append("")
    return "\n".join(lines).strip()
