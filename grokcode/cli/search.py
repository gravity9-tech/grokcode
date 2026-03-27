from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.table import Table

from grokcode.utils.ui import console, print_error

search_app = typer.Typer(help="Search the web or X using xAI native search.")


def _get_api_key() -> str:
    from grokcode.config.keychain import get_api_key

    key = get_api_key()
    if not key:
        print_error(
            "xAI API key not found.\n"
            "Run: [bold]grokcode config set xai_api_key <your-key>[/bold]"
        )
        raise typer.Exit(1)
    return key


@search_app.command("web")
def search_web(
    query: Annotated[str, typer.Argument(help="Search query")],
    max_results: Annotated[int, typer.Option("--max", "-n", help="Max results")] = 5,
) -> None:
    """Search the web (via xAI web search)."""
    asyncio.run(_search_web(query=query, max_results=max_results))


async def _search_web(query: str, max_results: int) -> None:
    from grokcode.search.search import web_search

    api_key = _get_api_key()
    with console.status(f"[cyan]Searching web: {query}[/cyan]"):
        try:
            results = await web_search(query=query, api_key=api_key, max_results=max_results)
        except Exception as e:
            print_error(f"Search failed: {e}")
            raise typer.Exit(1)

    _print_results(results, title=f'Web Search: "{query}"')


@search_app.command("x")
def search_x(
    query: Annotated[str, typer.Argument(help="Search query")],
    max_results: Annotated[int, typer.Option("--max", "-n", help="Max results")] = 5,
) -> None:
    """Search X (Twitter) for real-time signals."""
    asyncio.run(_search_x(query=query, max_results=max_results))


async def _search_x(query: str, max_results: int) -> None:
    from grokcode.search.search import x_search

    api_key = _get_api_key()
    with console.status(f"[cyan]Searching X: {query}[/cyan]"):
        try:
            results = await x_search(query=query, api_key=api_key, max_results=max_results)
        except Exception as e:
            print_error(f"X search failed: {e}")
            raise typer.Exit(1)

    _print_results(results, title=f'X Search: "{query}"')


def _print_results(results: list, title: str) -> None:
    from grokcode.search.search import SearchResult

    if not results:
        console.print("  [dim]No results found.[/dim]")
        return

    table = Table(title=title, border_style="dim", expand=False, show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Title / Summary", style="cyan", max_width=50)
    table.add_column("URL", style="blue", max_width=40)
    table.add_column("Source", style="dim", width=6)

    for i, r in enumerate(results, 1):
        assert isinstance(r, SearchResult)
        table.add_row(
            str(i),
            f"[bold]{r.title}[/bold]\n[dim]{r.snippet[:120]}[/dim]" if r.snippet else r.title,
            r.url[:40] if r.url else "[dim]—[/dim]",
            r.source,
        )

    console.print(table)
