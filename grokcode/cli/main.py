from __future__ import annotations

import asyncio
import sys
import traceback
from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel

from grokcode.cli.config_cmd import config_app
from grokcode.utils.ui import console, print_error, print_warning

app = typer.Typer(
    name="grokcode",
    help="Agentic coding CLI powered by xAI Grok",
    no_args_is_help=False,
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def default(ctx: typer.Context) -> None:
    """Launch interactive REPL when no subcommand is given."""
    if ctx.invoked_subcommand is None:
        from grokcode.cli.repl import run_repl
        from grokcode.config.config import get_config
        from grokcode.config.keychain import get_api_key

        config = get_config()
        api_key = get_api_key() or config.xai_api_key or ""
        run_repl(config, api_key)

app.add_typer(config_app, name="config")

# Lazily add sub-apps when modules are available
try:
    from grokcode.cli.workspace import workspace_app

    app.add_typer(workspace_app, name="workspace")
except ImportError:
    pass

try:
    from grokcode.cli.session import session_app

    app.add_typer(session_app, name="session")
except ImportError:
    pass

try:
    from grokcode.cli.search import search_app

    app.add_typer(search_app, name="search")
except ImportError:
    pass


@app.command()
def run(
    task: Annotated[str, typer.Argument(help="Task for the agent to perform")],
    resume: Annotated[bool, typer.Option("--resume", "-r", help="Resume last session")] = False,
    multi_agent: Annotated[
        bool, typer.Option("--multi-agent", "-m", help="Use multi-agent for complex tasks")
    ] = False,
    max_agents: Annotated[
        int, typer.Option("--max-agents", help="Max parallel sub-agents")
    ] = 5,
    auto_confirm: Annotated[
        bool, typer.Option("--auto-confirm", "-y", help="Auto-confirm all prompts")
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Enable debug logging")] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would be done without executing")
    ] = False,
    session_id: Annotated[
        str | None, typer.Option("--session-id", help="Resume a specific session by ID")
    ] = None,
) -> None:
    """Run an agentic coding task."""
    if debug:
        import logging

        logging.basicConfig(level=logging.DEBUG)

    try:
        asyncio.run(
            _run_task(
                task=task,
                resume=resume,
                multi_agent=multi_agent,
                max_agents=max_agents,
                auto_confirm=auto_confirm,
                debug=debug,
                dry_run=dry_run,
                session_id=session_id,
            )
        )
    except KeyboardInterrupt:
        console.print("\n  [dim]Interrupted — session saved. Resume with:[/dim] grokcode --resume")
    except Exception as e:
        _handle_top_level_error(e, debug)
        raise typer.Exit(1)


async def _run_task(
    task: str,
    resume: bool,
    multi_agent: bool,
    max_agents: int,
    auto_confirm: bool,
    debug: bool,
    dry_run: bool,
    session_id: str | None,
) -> None:
    from grokcode.config.config import get_config
    from grokcode.config.keychain import get_api_key

    config = get_config()

    # Resolve API key
    api_key = get_api_key() or config.xai_api_key
    if not api_key:
        print_error(
            "xAI API key not found.\n"
            "Run: [bold]grokcode config set xai_api_key <your-key>[/bold]\n"
            "Or set the [bold]XAI_API_KEY[/bold] environment variable."
        )
        raise typer.Exit(1)

    # Override auto_confirm from config if flag not set
    if not auto_confirm:
        auto_confirm = config.auto_confirm

    if multi_agent:
        from grokcode.agent.multi_agent import run_multi_agent

        result = await run_multi_agent(
            task=task,
            config=config,
            api_key=api_key,
            max_agents=max_agents,
            auto_confirm=auto_confirm,
            dry_run=dry_run,
        )
        console.print(
            Panel(
                f"[bold green]Multi-agent complete[/bold green]\n\n{result.summary}",
                border_style="green",
            )
        )
        return

    from grokcode.agent.agent import Agent, DoneEvent, ErrorEvent, ThinkingEvent, ToolCallEvent, ToolResultEvent
    from grokcode.agent.grok_client import GrokClient
    from grokcode.agent.tool_registry import ToolRegistry
    from grokcode.session.session import Session, get_last_session, load_session, save_session
    from grokcode.tools.bash import BashTool
    from grokcode.tools.fs import FS_TOOL_SCHEMAS, delete_file, edit_file, read_directory, read_file, write_file
    from grokcode.tools.git import GIT_TOOL_SCHEMAS, git_add, git_commit, git_create_branch, git_diff, git_log, git_status
    from grokcode.utils.ui import print_step, print_success, print_token_usage

    # Load prior session if resuming
    history = None
    prior_session: Session | None = None
    if session_id:
        prior_session = await load_session(session_id)
        history = [m.model_dump(mode="json") for m in prior_session.history]
        console.print(f"  [dim]Resuming session:[/dim] {session_id}")
    elif resume:
        prior_session = await get_last_session()
        if prior_session:
            history = [m.model_dump(mode="json") for m in prior_session.history]
            console.print(f"  [dim]Resuming last session:[/dim] {prior_session.id[:8]}...")

    # Build tool registry
    bash_tool = BashTool(auto_confirm=auto_confirm)
    registry = ToolRegistry()

    # File system tools
    registry.register("read_file", lambda path: read_file(path), FS_TOOL_SCHEMAS[0])
    registry.register("read_directory", lambda path, recursive=False: read_directory(path, recursive), FS_TOOL_SCHEMAS[1])
    registry.register("write_file", lambda path, content: write_file(path, content, auto_confirm), FS_TOOL_SCHEMAS[2])
    registry.register("edit_file", lambda path, old_str, new_str: edit_file(path, old_str, new_str), FS_TOOL_SCHEMAS[3])
    registry.register("delete_file", lambda path: delete_file(path, auto_confirm), FS_TOOL_SCHEMAS[4])

    # Bash tool
    registry.register("execute_bash", lambda command, timeout=30: bash_tool.execute(command, timeout), {
        "type": "function",
        "function": {
            "name": "execute_bash",
            "description": "Execute a shell command. Use for running tests, builds, installs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
                },
                "required": ["command"],
            },
        },
    })

    # Git tools
    registry.register("git_status", lambda: git_status(bash_tool), GIT_TOOL_SCHEMAS[0])
    registry.register("git_diff", lambda path=None: git_diff(bash_tool, path), GIT_TOOL_SCHEMAS[1])
    registry.register("git_add", lambda paths: git_add(bash_tool, paths), GIT_TOOL_SCHEMAS[2])
    registry.register("git_commit", lambda message: git_commit(bash_tool, message, auto_confirm), GIT_TOOL_SCHEMAS[3])
    registry.register("git_log", lambda n=10: git_log(bash_tool, n), GIT_TOOL_SCHEMAS[4])
    registry.register("git_create_branch", lambda name: git_create_branch(bash_tool, name), GIT_TOOL_SCHEMAS[5])

    # Search tools (always available — uses xAI native search)
    from grokcode.search.search import (
        format_results_as_tool_output,
        web_search,
        x_search,
    )

    async def _web_search(query: str) -> str:
        results = await web_search(query=query, api_key=api_key)
        return format_results_as_tool_output(results)

    async def _x_search(query: str) -> str:
        results = await x_search(query=query, api_key=api_key)
        return format_results_as_tool_output(results)

    registry.register("web_search", _web_search, {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for documentation, libraries, error messages, or Stack Overflow answers.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search query"}},
                "required": ["query"],
            },
        },
    })
    registry.register("x_search", _x_search, {
        "type": "function",
        "function": {
            "name": "x_search",
            "description": "Search X (Twitter) for real-time ecosystem signals, breaking changes, or community discussion.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search query"}},
                "required": ["query"],
            },
        },
    })

    # Workspace search tool (only if workspace is configured)
    if config.workspace_config and config.workspace_config.collection_id:
        from grokcode.workspace.collections_client import CollectionsClient
        from grokcode.search.search import format_results_as_tool_output

        _collection_id = config.workspace_config.collection_id

        async def _search_workspace(query: str) -> str:
            print_step("●", "Searching workspace knowledge...", style="magenta")
            async with CollectionsClient() as coll_client:
                results = await coll_client.query_collection(
                    collection_id=_collection_id,
                    query=query,
                    top_k=5,
                )
            if not results:
                return "No relevant workspace documents found."
            lines = []
            for r in results:
                source = r.metadata.get("path", r.doc_id or "workspace")
                lines.append(f"[Source: {source}]\n{r.content[:800]}")
            return "\n\n".join(lines)

        registry.register("search_workspace", _search_workspace, {
            "type": "function",
            "function": {
                "name": "search_workspace",
                "description": (
                    "Search the team's shared knowledge base (architecture docs, ADRs, coding standards). "
                    "Use this before implementing anything to ground your response in team conventions."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "What to search for"}},
                    "required": ["query"],
                },
            },
        })

    async with GrokClient(api_key=api_key, model=config.model, max_tokens=config.max_tokens) as client:
        agent = Agent(config=config, tool_registry=registry, grok_client=client)
        session = Session.new(task=task)
        total_input = 0
        total_output = 0

        try:
            async for event in agent.run(task=task, history=history, auto_confirm=auto_confirm, dry_run=dry_run):
                if isinstance(event, ThinkingEvent):
                    if event.text:
                        console.print(event.text, end="", highlight=False)
                elif isinstance(event, ToolCallEvent):
                    print_step("●", f"[cyan]{event.tool_name}[/cyan]({_fmt_args(event.arguments)})")
                elif isinstance(event, ToolResultEvent):
                    session.files_modified.extend(event.files_touched)
                    if event.tool_name in ("write_file", "edit_file", "delete_file"):
                        print_step("✎", f"Modified: {', '.join(event.files_touched)}", style="green")
                elif isinstance(event, DoneEvent):
                    console.print()  # newline after streaming
                    if event.text:
                        console.print(Panel(event.text, border_style="dim"))
                    session.status = "done"
                    session.history = agent.message_history
                    if event.usage:
                        total_input += event.usage.input_tokens
                        total_output += event.usage.output_tokens
                    print_success(f"Done — session [dim]{session.id[:8]}[/dim]")
                    if total_input or total_output:
                        print_token_usage(total_input, total_output)
                elif isinstance(event, ErrorEvent):
                    print_error(event.message)
                    session.status = "interrupted"

        except KeyboardInterrupt:
            session.status = "interrupted"
            console.print("\n  [dim]Interrupted[/dim]")

        finally:
            await save_session(session)
            if session.status == "interrupted":
                console.print(
                    f"  [dim]Session saved — resume with:[/dim] grokcode --resume"
                )


def _fmt_args(args: dict) -> str:
    """Format tool arguments for display, truncating long values."""
    parts = []
    for k, v in args.items():
        s = repr(v)
        if len(s) > 40:
            s = s[:37] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)


def _handle_top_level_error(exc: Exception, debug: bool) -> None:
    error_log = Path.home() / ".grokcode" / "error.log"
    error_log.parent.mkdir(parents=True, exist_ok=True)

    tb = traceback.format_exc()
    error_log.write_text(tb)

    if debug:
        console.print_exception()
    else:
        print_error(
            f"{type(exc).__name__}: {exc}\n\n"
            f"[dim]Details written to {error_log} — use --debug to print here[/dim]"
        )


@app.command("search")
def cmd_search(
    query: Annotated[str, typer.Argument(help="Web search query")],
    max_results: Annotated[int, typer.Option("--max", "-n")] = 5,
) -> None:
    """Search the web using xAI native web search."""
    asyncio.run(_standalone_search(query=query, tool="web", max_results=max_results))


@app.command("xsearch")
def cmd_xsearch(
    query: Annotated[str, typer.Argument(help="X (Twitter) search query")],
    max_results: Annotated[int, typer.Option("--max", "-n")] = 5,
) -> None:
    """Search X (Twitter) for real-time ecosystem signals."""
    asyncio.run(_standalone_search(query=query, tool="x", max_results=max_results))


async def _standalone_search(query: str, tool: str, max_results: int) -> None:
    from grokcode.config.keychain import get_api_key
    from grokcode.search.search import format_results_as_tool_output, web_search, x_search
    from grokcode.cli.search import _print_results

    api_key = get_api_key()
    if not api_key:
        print_error("xAI API key not found. Run: grokcode config set xai_api_key <key>")
        raise typer.Exit(1)

    label = "X" if tool == "x" else "Web"
    with console.status(f"[cyan]Searching {label}: {query}[/cyan]"):
        try:
            if tool == "x":
                results = await x_search(query=query, api_key=api_key, max_results=max_results)
            else:
                results = await web_search(query=query, api_key=api_key, max_results=max_results)
        except Exception as e:
            print_error(f"Search failed: {e}")
            raise typer.Exit(1)

    _print_results(results, title=f'{label} Search: "{query}"')


def main() -> None:
    app()


if __name__ == "__main__":
    main()
