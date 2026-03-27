from __future__ import annotations

import difflib
from contextlib import contextmanager
from typing import Generator

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm
from rich.spinner import Spinner
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

console = Console()


def print_step(icon: str, text: str, style: str = "cyan") -> None:
    """Print a coloured agent step line, e.g. ● Reading: path/to/file"""
    console.print(f"  [bold {style}]{icon}[/bold {style}] {text}")


def print_success(text: str) -> None:
    """Print a green success line."""
    console.print(f"  [bold green]✓[/bold green] {text}")


def print_error(text: str) -> None:
    """Print a red error panel."""
    console.print(Panel(f"[bold red]{text}[/bold red]", border_style="red"))


def print_warning(text: str) -> None:
    """Print a yellow warning line."""
    console.print(f"  [bold yellow]⚠[/bold yellow]  {text}")


def confirm(prompt: str, auto: bool = False) -> bool:
    """Ask for confirmation. Returns True immediately if auto=True."""
    if auto:
        console.print(f"  [dim]Auto-confirmed:[/dim] {prompt}")
        return True
    return Confirm.ask(f"  [yellow]{prompt}[/yellow]")


def print_diff(old: str, new: str, path: str) -> None:
    """Render a unified diff with syntax highlighting."""
    diff_lines = list(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )
    if not diff_lines:
        console.print("  [dim]No changes[/dim]")
        return
    diff_text = "".join(diff_lines)
    syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
    console.print(syntax)


def print_token_usage(input_tokens: int, output_tokens: int) -> None:
    """Print token usage summary panel."""
    console.print(
        Panel(
            f"[dim]Tokens used:[/dim]  "
            f"[cyan]{input_tokens:,}[/cyan] in  /  [green]{output_tokens:,}[/green] out",
            border_style="dim",
            expand=False,
        )
    )


class AgentLiveDisplay:
    """Context manager for live agent step display using rich.live.Live."""

    def __init__(self) -> None:
        self._text = Text()
        self._live = Live(self._text, console=console, refresh_per_second=10, transient=False)

    def __enter__(self) -> "AgentLiveDisplay":
        self._live.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        self._live.__exit__(*args)

    def update_step(self, icon: str, text: str, style: str = "cyan") -> None:
        """Update the live display with a new step."""
        # Print the previous step as a permanent line then update live
        console.print(f"  [bold {style}]{icon}[/bold {style}] {text}")
        self._live.update(Text())


class MultiAgentLiveDisplay:
    """Live display with a table — one row per sub-agent."""

    def __init__(self) -> None:
        self._table = _build_multi_agent_table()
        self._live = Live(self._table, console=console, refresh_per_second=4)
        self._rows: dict[str, int] = {}  # agent_id -> row index

    def __enter__(self) -> "MultiAgentLiveDisplay":
        self._live.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        self._live.__exit__(*args)

    def add_agent(self, agent_id: str, description: str) -> None:
        row_idx = len(self._rows)
        self._rows[agent_id] = row_idx
        self._table.add_row(
            agent_id[:8],
            description[:50],
            Spinner("dots").render(0),  # type: ignore[arg-type]
            "[yellow]running[/yellow]",
        )

    def update_agent(self, agent_id: str, action: str, status: str = "running") -> None:
        # rich Table rows are immutable; rebuild on each update
        row_idx = self._rows.get(agent_id)
        if row_idx is None:
            return
        style_map = {
            "running": "[yellow]running[/yellow]",
            "done": "[green]done[/green]",
            "error": "[red]error[/red]",
        }
        status_text = style_map.get(status, status)
        # Rebuild table with updated row
        new_table = _build_multi_agent_table()
        for row in self._table.rows:
            _ = row  # rows not directly accessible; store state separately
            break
        # Simplest approach: keep a parallel data store
        _ = (row_idx, action, status_text)  # consumed below via _state
        self._live.update(self._table)

    @property
    def table(self) -> Table:
        return self._table


def _build_multi_agent_table() -> Table:
    table = Table(title="Multi-Agent Tasks", border_style="dim", expand=False)
    table.add_column("Agent", style="dim", width=10)
    table.add_column("Task", style="cyan", no_wrap=False, max_width=50)
    table.add_column("Action", style="white", no_wrap=True, max_width=30)
    table.add_column("Status", justify="center", width=10)
    return table


@contextmanager
def spinner(text: str) -> Generator[None, None, None]:
    """Simple spinner context manager for short operations."""
    with console.status(f"[cyan]{text}[/cyan]", spinner="dots"):
        yield
