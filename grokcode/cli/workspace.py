from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from grokcode.utils.ui import confirm, console, print_error, print_success, print_warning

workspace_app = typer.Typer(help="Manage the team workspace (shared knowledge base).")


def _get_client() -> object:
    """Build a CollectionsClient (local-backed — no API key required)."""
    from grokcode.workspace.collections_client import CollectionsClient

    return CollectionsClient()


def _require_workspace_config():  # type: ignore[return]
    """Load workspace config or exit with a helpful error."""
    from grokcode.config.config import load_workspace_config

    ws = load_workspace_config()
    if not ws:
        print_error(
            "No workspace found in this directory.\n"
            "Run: [bold]grokcode workspace init --name <name>[/bold]"
        )
        raise typer.Exit(1)
    return ws


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@workspace_app.command("init")
def workspace_init(
    name: Annotated[str, typer.Option("--name", "-n", help="Workspace name")] = "",
    team_id: Annotated[str, typer.Option("--team-id", help="Team identifier")] = "default",
) -> None:
    """Initialize a team workspace (creates an xAI Collection)."""
    if not name:
        name = typer.prompt("Workspace name")

    asyncio.run(_workspace_init(name=name, team_id=team_id))


async def _workspace_init(name: str, team_id: str) -> None:
    from grokcode.workspace.collections_client import CollectionsClient
    from grokcode.workspace.workspace import init_workspace

    client: CollectionsClient = _get_client()  # type: ignore[assignment]
    with console.status(f"[cyan]Creating workspace '{name}'...[/cyan]"):
        try:
            workspace_data = await init_workspace(name=name, team_id=team_id, client=client)
        except Exception as e:
            print_error(f"Failed to create workspace: {e}")
            raise typer.Exit(1)

    console.print(
        Panel(
            f"[bold green]Workspace created: {name}[/bold green]\n\n"
            f"[dim]Collection ID:[/dim]  {workspace_data['collection_id']}\n"
            f"[dim]Team ID:[/dim]        {team_id}\n\n"
            "Next steps:\n"
            "  1. [cyan]git add grokcode.workspace.json && git commit -m 'Add workspace config'[/cyan]\n"
            "  2. [cyan]grokcode workspace index ./docs ./README.md[/cyan]",
            border_style="green",
            title="Workspace Initialized",
        )
    )


# ---------------------------------------------------------------------------
# index
# ---------------------------------------------------------------------------


@workspace_app.command("index")
def workspace_index(
    paths: Annotated[list[Path], typer.Argument(help="Files or directories to index")],
    tag: Annotated[str, typer.Option("--tag", "-t", help="Metadata tag for these documents")] = "",
) -> None:
    """Index files into the team knowledge base."""
    asyncio.run(_workspace_index(paths=paths, tag=tag))


async def _workspace_index(paths: list[Path], tag: str) -> None:
    from grokcode.workspace.collections_client import CollectionsClient
    from grokcode.workspace.workspace import INDEXABLE_EXTENSIONS, _collect_files, index_paths

    ws = _require_workspace_config()
    if not ws.collection_id:
        print_error("Workspace has no collection_id. Re-run `grokcode workspace init`.")
        raise typer.Exit(1)

    # Collect files first for progress reporting
    all_files = _collect_files(paths)
    eligible = [
        f for f in all_files
        if f.stat().st_size <= 100 * 1024
        and f.suffix.lower() in INDEXABLE_EXTENSIONS
    ]
    oversized = [f for f in all_files if f.stat().st_size > 100 * 1024]

    if not eligible:
        print_warning("No eligible files found to index.")
        return

    console.print(f"  [dim]Found {len(eligible)} file(s) to index[/dim]")
    if oversized:
        for f in oversized:
            print_warning(f"Skipping (>100KB): {f}")

    client: CollectionsClient = _get_client()  # type: ignore[assignment]

    uploaded_count = 0
    failed: list[str] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Indexing...", total=len(eligible))

        for file_path in eligible:
            progress.update(task, description=f"Uploading: {file_path.name}")
            try:
                content = file_path.read_text(errors="replace")
                metadata = {"path": str(file_path)}
                if tag:
                    metadata["tag"] = tag
                await client.upload_document(
                    collection_id=ws.collection_id,
                    content=content,
                    metadata=metadata,
                )
                from grokcode.workspace.workspace import _persist_doc_id

                uploaded_count += 1
            except Exception as e:
                failed.append(f"{file_path}: {e}")
            finally:
                progress.advance(task)

    await client.close()

    print_success(f"Indexed {uploaded_count}/{len(eligible)} files into workspace '{ws.workspace}'")
    if failed:
        for f in failed:
            print_warning(f"Failed: {f}")


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@workspace_app.command("list")
def workspace_list() -> None:
    """List all documents in the team knowledge base."""
    asyncio.run(_workspace_list())


async def _workspace_list() -> None:
    from grokcode.workspace.collections_client import CollectionsClient

    ws = _require_workspace_config()
    client: CollectionsClient = _get_client()  # type: ignore[assignment]

    try:
        with console.status("[cyan]Fetching documents...[/cyan]"):
            docs = await client.list_documents(ws.collection_id)
    except Exception as e:
        print_error(f"Failed to list documents: {e}")
        raise typer.Exit(1)
    finally:
        await client.close()

    if not docs:
        console.print("  [dim]No documents indexed yet.[/dim]")
        return

    table = Table(title=f"Workspace: {ws.workspace}", border_style="dim", expand=False)
    table.add_column("Doc ID", style="dim", width=20)
    table.add_column("Path / Name", style="cyan", max_width=60)
    table.add_column("Indexed", style="dim", width=20)

    for doc in docs:
        path = doc.metadata.get("path", doc.id)
        table.add_row(
            doc.id[:18],
            path,
            doc.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)
    console.print(f"  [dim]Total: {len(docs)} document(s)[/dim]")


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------


@workspace_app.command("remove")
def workspace_remove(
    doc_id: Annotated[str, typer.Option("--doc-id", help="Document ID to remove")],
) -> None:
    """Remove a document from the team knowledge base."""
    asyncio.run(_workspace_remove(doc_id=doc_id))


async def _workspace_remove(doc_id: str) -> None:
    from grokcode.workspace.collections_client import CollectionsClient
    from grokcode.workspace.workspace import remove_document

    ws = _require_workspace_config()

    approved = confirm(f"Remove document [bold]{doc_id}[/bold] from workspace?", auto=False)
    if not approved:
        console.print("  [dim]Cancelled.[/dim]")
        return

    client: CollectionsClient = _get_client()  # type: ignore[assignment]

    try:
        with console.status("[cyan]Removing document...[/cyan]"):
            await remove_document(
                collection_id=ws.collection_id,
                doc_id=doc_id,
                client=client,
            )
    except Exception as e:
        print_error(f"Failed to remove document: {e}")
        raise typer.Exit(1)
    finally:
        await client.close()

    print_success(f"Removed document: {doc_id}")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@workspace_app.command("status")
def workspace_status() -> None:
    """Show workspace health and statistics."""
    asyncio.run(_workspace_status())


async def _workspace_status() -> None:
    from grokcode.workspace.collections_client import CollectionsClient
    from grokcode.workspace.workspace import load_workspace_index

    ws = _require_workspace_config()
    client: CollectionsClient = _get_client()  # type: ignore[assignment]

    doc_count = 0
    collection_name = ws.workspace
    error_msg = ""

    try:
        with console.status("[cyan]Checking workspace status...[/cyan]"):
            collection = await client.get_collection(ws.collection_id)
            collection_name = collection.name
            docs = await client.list_documents(ws.collection_id)
            doc_count = len(docs)
    except Exception as e:
        error_msg = str(e)
    finally:
        await client.close()

    local_index = load_workspace_index()

    status_color = "red" if error_msg else "green"
    status_text = f"[{status_color}]{'error' if error_msg else 'healthy'}[/{status_color}]"

    content = (
        f"[dim]Workspace:[/dim]     {ws.workspace}\n"
        f"[dim]Team ID:[/dim]       {ws.team_id}\n"
        f"[dim]Collection ID:[/dim] {ws.collection_id}\n"
        f"[dim]Status:[/dim]        {status_text}\n"
        f"[dim]Documents:[/dim]     {doc_count} indexed\n"
        f"[dim]Local index:[/dim]   {len(local_index)} tracked files\n"
        f"[dim]Rules:[/dim]         {len(ws.rules)} defined\n"
        f"[dim]MCP servers:[/dim]   {len(ws.mcp_servers)} configured"
    )
    if error_msg:
        content += f"\n\n[red]Error:[/red] {error_msg}"
    if ws.rules:
        content += "\n\n[dim]Active rules:[/dim]\n" + "\n".join(f"  • {r}" for r in ws.rules)

    console.print(Panel(content, border_style=status_color, title="Workspace Status"))
