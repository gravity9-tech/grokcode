from __future__ import annotations

import asyncio

import typer
from rich.table import Table

from grokcode.utils.ui import console

session_app = typer.Typer(help="Manage GrokCode sessions.")


@session_app.command("list")
def session_list() -> None:
    """List all saved sessions."""
    asyncio.run(_session_list())


async def _session_list() -> None:
    from grokcode.session.session import list_sessions

    sessions = await list_sessions()
    if not sessions:
        console.print("  [dim]No sessions found.[/dim]")
        return

    table = Table(title="Sessions", border_style="dim", expand=False)
    table.add_column("ID", style="dim", width=10)
    table.add_column("Task", style="cyan", max_width=50)
    table.add_column("Status", justify="center", width=12)
    table.add_column("Started", style="dim", width=20)
    table.add_column("Tokens", justify="right", width=12)

    status_styles = {"done": "green", "active": "yellow", "interrupted": "red"}

    for s in sessions:
        style = status_styles.get(s.status, "white")
        tokens = ""
        if s.token_usage:
            tokens = f"{s.token_usage.input_tokens + s.token_usage.output_tokens:,}"
        table.add_row(
            s.id[:8],
            s.task[:50],
            f"[{style}]{s.status}[/{style}]",
            s.started_at.strftime("%Y-%m-%d %H:%M"),
            tokens,
        )

    console.print(table)


@session_app.command("export")
def session_export(
    name: str = typer.Option(..., "--name", "-n", help="Name for the session snapshot"),
    session_id: str | None = typer.Option(None, "--session-id", help="Session ID (default: last)"),
) -> None:
    """Export a session for teammate handoff."""
    asyncio.run(_session_export(name=name, session_id=session_id))


async def _session_export(name: str, session_id: str | None) -> None:
    from grokcode.session.handoff import export_session

    bundle = await export_session(session_id=session_id, name=name)
    console.print(
        f"  [green]✓[/green] Session exported as [bold]{name}[/bold]  "
        f"({len(bundle.session.history)} messages, {len(bundle.files_snapshot)} files)"
    )
    console.print(
        f"  [dim]Share:[/dim] .grokcode/handoffs/{name}.json"
    )


@session_app.command("import")
def session_import(
    name: str = typer.Argument(..., help="Session snapshot name to import"),
) -> None:
    """Import a teammate's session snapshot."""
    asyncio.run(_session_import(name=name))


async def _session_import(name: str) -> None:
    from grokcode.session.handoff import import_session
    from grokcode.session.session import save_session
    from rich.panel import Panel

    session = await import_session(name=name)
    await save_session(session)

    console.print(
        Panel(
            f"[bold]Imported:[/bold] {name}\n"
            f"[dim]Original task:[/dim] {session.task}\n"
            f"[dim]Messages:[/dim] {len(session.history)}\n\n"
            f"Resume with: [bold cyan]grokcode --resume[/bold cyan]",
            border_style="cyan",
            title="Session Imported",
        )
    )
