from __future__ import annotations

import asyncio
import getpass
from pathlib import Path

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from grokcode.config.config import AppConfig
from grokcode.utils.ui import console

# Brand colors
PINK = "#e31c79"
BLUE = "#326295"
TEAL = "#49C5B1"

VERSION = "0.1.0"


def _xai_logo() -> Text:
    """Build the xAI logo as a white Rich Text object with lowercase x."""
    logo = Text(justify="center")
    # Row 1  (x uses ╲ ╱ style for lowercase feel)
    logo.append("██╗", style="white")
    logo.append("  ")
    logo.append("██╗", style="white")
    logo.append(" ")
    logo.append("█████╗", style="white")
    logo.append("  ")
    logo.append("██╗\n", style="white")
    # Row 2
    logo.append(" ╚██╗", style="white")
    logo.append("██╔╝", style="white")
    logo.append(" ")
    logo.append("██╔══██╗", style="white")
    logo.append(" ")
    logo.append("██║\n", style="white")
    # Row 3  (x narrows to a point — lowercase x mid)
    logo.append("  ╚██╔╝", style="white")
    logo.append("  ")
    logo.append("███████║", style="white")
    logo.append(" ")
    logo.append("██║\n", style="white")
    # Row 4  (x widens back out)
    logo.append("  ██╔██╗", style="white")
    logo.append("  ")
    logo.append("██╔══██║", style="white")
    logo.append(" ")
    logo.append("██║\n", style="white")
    # Row 5
    logo.append(" ██╔╝ ██╗", style="white")
    logo.append(" ")
    logo.append("██║  ██║", style="white")
    logo.append(" ")
    logo.append("██║\n", style="white")
    # Row 6
    logo.append(" ╚═╝  ╚═╝", style="white")
    logo.append(" ")
    logo.append("╚═╝  ╚═╝", style="white")
    logo.append(" ")
    logo.append("╚═╝", style="white")
    return logo


GROKCODE_MD_TEMPLATE = """\
# {project} — GrokCode Instructions

## Stack
- Describe your tech stack here (e.g. FastAPI + Redis + PostgreSQL)

## Conventions
- List your coding conventions here
- e.g. Services in src/services/ — no HTTP concerns
- e.g. Tests use pytest-asyncio with httpx.AsyncClient

## Rules
- Any rules Grok should always follow in this project
"""

SLASH_HELP = {
    "Agent": [
        ("<task>", "Run an agentic coding task"),
        ("/multi-agent <task>", "Run task with parallel sub-agents"),
        ("/dry-run <task>", "Show what the agent would do without executing"),
        ("/resume", "Resume the last session"),
        ("/resume <id>", "Resume a specific session by ID"),
    ],
    "Search": [
        ("/search <query>", "Search the web via xAI"),
        ("/xsearch <query>", "Search X (Twitter) for real-time signals"),
    ],
    "Session": [
        ("/sessions", "List all saved sessions"),
        ("/session export <n>", "Export current session for teammate handoff"),
        ("/session import <n>", "Import a teammate's exported session"),
    ],
    "Workspace": [
        ("/workspace", "Show workspace status"),
        ("/workspace init <n>", "Create a new team workspace"),
        ("/workspace index <p>", "Index files into the team knowledge base"),
        ("/workspace list", "List indexed documents"),
    ],
    "Config": [
        ("/config", "Show current configuration"),
        ("/config model", "Interactively select the Grok model"),
        ("/config set <k> <v>", "Set a config value (e.g. theme, max_tokens)"),
    ],
    "MCP Servers": [
        ("/mcp", "Show configured MCP servers and auth status"),
        ("/mcp catalog", "Browse popular MCP servers to install"),
        ("/mcp add <n> <url>", "Add an MCP server (prompts for auth token)"),
        ("/mcp auth <name>", "Set or update the auth token for a server"),
        ("/mcp remove <name>", "Remove an MCP server and its token"),
        ("/mcp test <name>", "Test connection and list available tools"),
    ],
    "Onboarding": [
        ("/onboard", "Generate an onboarding audio guide for this codebase"),
        ("/onboard --no-audio", "Generate onboarding script only (no audio)"),
        ("/onboard --voice <v>", "Choose voice for audio (default: alloy)"),
    ],
    "General": [
        ("/init", "Create a GROKCODE.md with instructions for Grok"),
        ("/help", "Show this help"),
        ("/exit, /quit", "Exit GrokCode"),
    ],
}


def _shorten_path(p: Path) -> str:
    home = Path.home()
    try:
        return "~/" + str(p.relative_to(home))
    except ValueError:
        return str(p)


def show_welcome(config: AppConfig, username: str) -> None:
    """Render the Claude Code-style welcome screen."""
    from grokcode.session.session import list_sessions

    sessions = asyncio.run(list_sessions())

    model = config.model
    team = (config.workspace_config.team_id if config.workspace_config else None) or "no workspace"
    cwd = _shorten_path(Path.cwd())

    # ── Left cell ────────────────────────────────────────────────────────────
    left = Text(justify="center")
    left.append(f"\nWelcome back {username}!\n\n", style=f"bold {PINK}")
    left.append(_xai_logo())
    left.append(f"\n\n{model} · {team}\n{cwd}", style=PINK)

    # ── Right cell ───────────────────────────────────────────────────────────
    right = Text()
    right.append("Tips for getting started\n", style=f"bold {PINK}")
    right.append("─" * 36 + "\n", style=PINK)
    right.append("Run /init to create a GROKCODE.md\n", style=TEAL)
    right.append("file with instructions for Grok\n\n", style=TEAL)
    right.append("Type any task to run the agent\n", style=TEAL)
    right.append("/help for all commands\n\n", style=f"dim {TEAL}")

    right.append("Recent activity\n", style=f"bold {PINK}")
    right.append("─" * 36 + "\n", style=PINK)

    if sessions:
        for s in sessions[:3]:
            task_preview = s.task[:45] + ("…" if len(s.task) > 45 else "")
            date_str = s.started_at.strftime("%Y-%m-%d")
            right.append(f"{task_preview}\n", style=TEAL)
            right.append(f"  {date_str}\n", style="dim")
    else:
        right.append("No recent activity\n", style="dim")

    # ── Two-column table inside a branded panel ───────────────────────────────
    grid = Table.grid(expand=True, padding=(0, 2))
    grid.add_column(ratio=2)  # left: logo + info
    grid.add_column(ratio=3)  # right: tips + activity
    grid.add_row(left, right)

    outer = Panel(
        grid,
        title=Text(f"GrokCode v{VERSION}", style=f"bold {PINK}"),
        border_style=PINK,
    )
    console.print(outer)


def _print_help() -> None:
    table = Table(border_style="dim", expand=False, show_header=False, padding=(0, 2))
    table.add_column("Command", style=TEAL, width=26)
    table.add_column("Description", style="white")
    for section, entries in SLASH_HELP.items():
        table.add_row(f"[bold {PINK}]{section}[/]", "", end_section=False)
        for cmd, desc in entries:
            table.add_row(f"  {cmd}", desc)
    console.print(table)


def _init_grokcode_md() -> None:
    path = Path.cwd() / "GROKCODE.md"
    if path.exists():
        console.print(f"  [dim]GROKCODE.md already exists: {path}[/dim]")
        return
    project = Path.cwd().name
    path.write_text(GROKCODE_MD_TEMPLATE.format(project=project))
    console.print(
        f"  [{TEAL}]✓ Created GROKCODE.md — edit it to add project instructions for Grok[/]"
    )


def _show_sessions() -> None:
    from grokcode.session.session import list_sessions

    sessions = asyncio.run(list_sessions())
    if not sessions:
        console.print("  [dim]No sessions found.[/dim]")
        return

    table = Table(title="Sessions", border_style="dim", expand=False)
    table.add_column("ID", style="dim", width=10)
    table.add_column("Task", style=TEAL, max_width=50)
    table.add_column("Status", justify="center", width=12)
    table.add_column("Started", style="dim", width=16)

    status_styles = {"done": "green", "active": "yellow", "interrupted": "red"}
    for s in sessions:
        style = status_styles.get(s.status, "white")
        table.add_row(
            s.id[:8],
            s.task[:50],
            f"[{style}]{s.status}[/{style}]",
            s.started_at.strftime("%Y-%m-%d %H:%M"),
        )
    console.print(table)


def _show_workspace(config: AppConfig) -> None:
    if not config.workspace_config:
        console.print(
            "  [dim]No workspace configured. Run:[/dim] grokcode workspace init --name <name>"
        )
        return
    ws = config.workspace_config
    console.print(
        Panel(
            f"[bold {PINK}]{ws.workspace}[/]\n"
            f"[dim]Team:[/dim] {ws.team_id}\n"
            f"[dim]Collection:[/dim] {ws.collection_id}",
            title="Workspace",
            border_style=BLUE,
        )
    )


def _session_export(name: str) -> None:
    from grokcode.cli.session import _session_export as _do

    asyncio.run(_do(name=name, session_id=None))


def _session_import(name: str) -> None:
    from grokcode.cli.session import _session_import as _do

    asyncio.run(_do(name=name))


def _workspace_init_cmd(name: str) -> None:
    from grokcode.cli.workspace import _workspace_init as _do

    asyncio.run(_do(name=name, team_id="default"))


def _workspace_index_cmd(paths_str: str) -> None:
    from grokcode.cli.workspace import _workspace_index as _do

    paths = [Path(p) for p in paths_str.split()]
    asyncio.run(_do(paths=paths, tag=""))


def _workspace_list_cmd() -> None:
    from grokcode.cli.workspace import _workspace_list as _do

    asyncio.run(_do())


def _show_config() -> None:
    from grokcode.cli.config_cmd import config_show

    config_show()


def _config_set_cmd(key: str, value: str) -> None:
    from grokcode.cli.config_cmd import config_set

    config_set(key, value)


AVAILABLE_MODELS = [
    ("grok-4", "Most capable — best for complex coding tasks"),
    ("grok-3", "Powerful and precise"),
    ("grok-3-fast", "Faster grok-3 with lower latency"),
    ("grok-3-mini", "Efficient — great for everyday tasks (default)"),
    ("grok-3-mini-fast", "Fastest response, lightweight tasks"),
    ("grok-2-1212", "Previous generation, stable"),
    ("grok-2-vision-1212", "Previous generation with vision support"),
]


def _select_model(config: AppConfig) -> None:
    """Interactive model selector — show list, prompt for choice, save."""
    from grokcode.config.config import load_user_config, save_user_config

    current = config.model

    table = Table(border_style="dim", expand=False, show_header=False, padding=(0, 2))
    table.add_column("#", style=f"bold {PINK}", width=4)
    table.add_column("Model", style="white", width=22)
    table.add_column("Description", style=f"dim {TEAL}")

    for i, (name, desc) in enumerate(AVAILABLE_MODELS, 1):
        marker = f"[bold {TEAL}]▶[/]" if name == current else " "
        table.add_row(f"{marker}{i}", name, desc)

    console.print(f"\n  Current model: [bold {PINK}]{current}[/]\n")
    console.print(table)
    console.print("\n  [dim]Enter a number to switch model, or press Enter to keep current:[/dim]")

    try:
        choice = input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if not choice:
        console.print(f"  [dim]Model unchanged: {current}[/dim]")
        return

    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(AVAILABLE_MODELS)):
            raise ValueError
    except ValueError:
        console.print(
            f"  [red]Invalid selection.[/red] Enter a number between 1 and {len(AVAILABLE_MODELS)}."
        )
        return

    new_model = AVAILABLE_MODELS[idx][0]
    if new_model == current:
        console.print(f"  [dim]Model unchanged: {current}[/dim]")
        return

    user_config = load_user_config()
    user_config.model = new_model
    save_user_config(user_config)
    config.model = new_model  # update in-memory config for this session
    console.print(f"  [{TEAL}]✓ Model updated:[/] [bold]{new_model}[/bold]")


# ---------------------------------------------------------------------------
# MCP server management
# ---------------------------------------------------------------------------

MCP_CATALOG: list[tuple[str, str, str, str, str]] = [
    # (name, label, description, url, token_hint)
    (
        "confluence",
        "Atlassian Confluence + Jira",
        "Pages, spaces, issues & PRs",
        "https://mcp.atlassian.com/v1/mcp",
        "Atlassian API token — generate at: id.atlassian.com/manage-profile/security/api-tokens",
    ),
    (
        "github",
        "GitHub",
        "Repos, PRs, issues & code search",
        "https://api.githubcopilot.com/mcp/",
        "GitHub personal access token — generate at: github.com/settings/tokens",
    ),
    (
        "linear",
        "Linear",
        "Issues, projects & cycles",
        "https://mcp.linear.app/sse",
        "Linear API key — generate at: linear.app/settings/api",
    ),
    (
        "slack",
        "Slack",
        "Messages, channels & search",
        "https://mcp.slack.com/v1/mcp",
        "Slack bot token (xoxb-...) — create at: api.slack.com/apps",
    ),
    (
        "notion",
        "Notion",
        "Pages, databases & blocks",
        "https://mcp.notion.com/v1/mcp",
        "Notion integration token — create at: notion.so/my-integrations",
    ),
    (
        "sentry",
        "Sentry",
        "Errors, issues & releases",
        "https://mcp.sentry.io/v1/mcp",
        "Sentry auth token — generate at: sentry.io/settings/auth-tokens/",
    ),
    (
        "datadog",
        "Datadog",
        "Metrics, logs & monitors",
        "https://mcp.datadoghq.com/v1/mcp",
        "Datadog API key — generate at: app.datadoghq.com/organization-settings/api-keys",
    ),
]

# Tokens are stored in ~/.grokcode/mcp_tokens.json, NOT in workspace JSON (which is git-committed)
_MCP_TOKENS_PATH = Path.home() / ".grokcode" / "mcp_tokens.json"


def _load_mcp_tokens() -> dict[str, str]:
    """Load {server_name: token} from ~/.grokcode/mcp_tokens.json."""
    import json

    if not _MCP_TOKENS_PATH.exists():
        return {}
    try:
        return json.loads(_MCP_TOKENS_PATH.read_text())
    except Exception:
        return {}


def _save_mcp_tokens(tokens: dict[str, str]) -> None:
    """Persist tokens dict to ~/.grokcode/mcp_tokens.json (mode 600)."""
    import json
    import os

    _MCP_TOKENS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MCP_TOKENS_PATH.write_text(json.dumps(tokens, indent=2))
    os.chmod(_MCP_TOKENS_PATH, 0o600)


def _save_workspace_config(ws: object) -> None:
    """Persist updated WorkspaceConfig back to grokcode.workspace.json in cwd."""
    import json

    from grokcode.config.config import WORKSPACE_CONFIG_FILENAME, WorkspaceConfig

    wsc: WorkspaceConfig = ws  # type: ignore[assignment]
    path = Path.cwd() / WORKSPACE_CONFIG_FILENAME
    path.write_text(json.dumps(wsc.model_dump(), indent=2))


def _prompt_token(name: str, hint: str) -> str | None:
    """Prompt the user for an auth token, showing where to get it."""
    import getpass as _gp

    console.print(f"\n  [bold {PINK}]Authentication required[/]")
    console.print(f"  [dim]{hint}[/dim]\n")
    console.print("  [dim]Paste your token below (input is hidden):[/dim]")
    try:
        token = _gp.getpass("  Token: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not token:
        console.print(
            f"  [dim]Skipped — no token entered. You can add it later with /mcp auth {name}[/dim]"
        )
        return None
    return token


def _mcp_list(config: AppConfig) -> None:
    """Show all MCP servers configured in the current workspace."""
    ws = config.workspace_config
    if not ws:
        console.print(
            "  [dim]No workspace configured. Run[/dim] /workspace init <name> [dim]first.[/dim]"
        )
        return

    tokens = _load_mcp_tokens()
    console.print(f"\n  [bold {PINK}]MCP Servers[/] — {ws.workspace}\n")

    if not ws.mcp_servers:
        console.print("  [dim]No MCP servers configured.[/dim]")
        console.print("  [dim]Browse available servers with[/dim] /mcp catalog")
        console.print("  [dim]Add one with[/dim] /mcp add <name> <url>")
        return

    table = Table(border_style="dim", expand=False, show_header=True, padding=(0, 2))
    table.add_column("Name", style=f"bold {TEAL}", width=16)
    table.add_column("URL", style="white", max_width=45)
    table.add_column("Auth", justify="center", width=8)

    for srv in ws.mcp_servers:
        auth_status = f"[{TEAL}]✓[/]" if srv.name in tokens else "[yellow]none[/]"
        table.add_row(srv.name, srv.url, auth_status)

    console.print(table)
    console.print("\n  [dim]Auth ✓ = token saved · none = set with[/dim] /mcp auth <name>")
    console.print("  [dim]Test:[/dim] /mcp test <name>  [dim]· Remove:[/dim] /mcp remove <name>")


def _mcp_catalog(config: AppConfig) -> None:
    """Show popular MCP servers and allow the user to install one."""
    configured_names = set()
    if config.workspace_config:
        configured_names = {s.name for s in config.workspace_config.mcp_servers}

    table = Table(border_style="dim", expand=False, show_header=False, padding=(0, 2))
    table.add_column("#", style=f"bold {PINK}", width=4)
    table.add_column("Service", style=f"bold {TEAL}", width=22)
    table.add_column("Description", style="white", width=32)

    for i, (name, label, desc, _url, _hint) in enumerate(MCP_CATALOG, 1):
        marker = f"[{TEAL}]✓[/] " if name in configured_names else "  "
        table.add_row(f"{marker}{i}", label, desc)

    console.print(f"\n  [bold {PINK}]Popular MCP Servers[/]\n")
    console.print(table)
    console.print("\n  [dim]Enter a number to install, or press Enter to cancel:[/dim]")

    try:
        choice = input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if not choice:
        return

    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(MCP_CATALOG)):
            raise ValueError
    except ValueError:
        console.print("  [red]Invalid selection.[/red]")
        return

    name, label, _desc, url, hint = MCP_CATALOG[idx]

    if name in configured_names:
        console.print(f"  [dim]{label} is already installed.[/dim]")
        return

    _mcp_add(name, url, config, token_hint=hint)


def _mcp_add(name: str, url: str, config: AppConfig, token_hint: str = "") -> None:
    """Add an MCP server and prompt for its auth token."""
    from grokcode.config.config import McpServer

    ws = config.workspace_config
    if not ws:
        console.print("  [red]No workspace configured.[/red] Run /workspace init <name> first.")
        return

    existing = [s.name for s in ws.mcp_servers]
    if name in existing:
        console.print(f"  [dim]MCP server '{name}' is already configured.[/dim]")
        return

    # Prompt for token
    hint = token_hint or f"Provide an auth token for {name} (or press Enter to skip and add later)"
    token = _prompt_token(name, hint)

    # Save server to workspace config
    ws.mcp_servers.append(McpServer(name=name, url=url))
    _save_workspace_config(ws)
    config.workspace_config = ws

    # Save token separately (never in workspace JSON)
    if token:
        tokens = _load_mcp_tokens()
        tokens[name] = token
        _save_mcp_tokens(tokens)
        auth_note = f"[{TEAL}]✓ Token saved securely (~/.grokcode/mcp_tokens.json)[/]"
    else:
        auth_note = f"[yellow]⚠  No token — add later with:[/yellow] /mcp auth {name}"

    console.print(f"\n  [{TEAL}]✓ Added MCP server:[/] [bold]{name}[/] → {url}")
    console.print(
        "  [dim]Saved to grokcode.workspace.json (URL only — token is never committed)[/dim]"
    )
    console.print(f"  {auth_note}")
    console.print(f"  [dim]Test with:[/dim] /mcp test {name}")


def _mcp_auth(name: str, config: AppConfig) -> None:
    """Set or update the auth token for an already-configured MCP server."""
    ws = config.workspace_config
    if not ws:
        console.print("  [red]No workspace configured.[/red]")
        return

    srv = next((s for s in ws.mcp_servers if s.name == name), None)
    if not srv:
        console.print(
            f"  [red]MCP server '{name}' not found.[/red] Add it first with /mcp add or /mcp catalog"
        )
        return

    # Find hint from catalog if available
    hint = next((h for n, _l, _d, _u, h in MCP_CATALOG if n == name), f"Auth token for {name}")
    token = _prompt_token(name, hint)

    if not token:
        return

    tokens = _load_mcp_tokens()
    tokens[name] = token
    _save_mcp_tokens(tokens)
    console.print(f"  [{TEAL}]✓ Token updated for {name}[/]")
    console.print(f"  [dim]Run[/dim] /mcp test {name} [dim]to verify.[/dim]")


def _mcp_remove(name: str, config: AppConfig) -> None:
    """Remove an MCP server and its token."""
    ws = config.workspace_config
    if not ws:
        console.print("  [red]No workspace configured.[/red]")
        return

    before = len(ws.mcp_servers)
    ws.mcp_servers = [s for s in ws.mcp_servers if s.name != name]

    if len(ws.mcp_servers) == before:
        console.print(f"  [red]MCP server '{name}' not found.[/red]")
        names = ", ".join(s.name for s in ws.mcp_servers) or "none"
        console.print(f"  [dim]Configured servers: {names}[/dim]")
        return

    _save_workspace_config(ws)
    config.workspace_config = ws

    # Also remove stored token
    tokens = _load_mcp_tokens()
    if name in tokens:
        del tokens[name]
        _save_mcp_tokens(tokens)

    console.print(f"  [{TEAL}]✓ Removed MCP server:[/] {name} [dim](token deleted)[/dim]")


def _mcp_test(name: str, config: AppConfig) -> None:
    """Test connectivity to an MCP server and list its available tools."""
    from grokcode.tools.mcp_client import discover_tools

    ws = config.workspace_config
    if not ws:
        console.print("  [red]No workspace configured.[/red]")
        return

    srv = next((s for s in ws.mcp_servers if s.name == name), None)
    if not srv:
        console.print(f"  [red]MCP server '{name}' not found.[/red]")
        names = ", ".join(s.name for s in ws.mcp_servers) or "none"
        console.print(f"  [dim]Configured: {names}[/dim]")
        return

    tokens = _load_mcp_tokens()
    token = tokens.get(name)

    if not token:
        console.print(
            f"  [yellow]⚠[/yellow]  No auth token for [bold]{name}[/bold]. "
            f"Set one with: /mcp auth {name}"
        )
        console.print("  [dim]Attempting unauthenticated connection...[/dim]")

    console.print(f"  [dim]Testing {name} → {srv.url}[/dim]")

    async def _do() -> list[dict]:
        return await discover_tools(server_url=srv.url, api_key=token)

    try:
        with console.status(f"[{TEAL}]Connecting to {name}...[/]"):
            tools = asyncio.run(_do())
    except Exception as e:
        console.print(f"  [red]Connection failed:[/red] {e}")
        return

    if not tools:
        console.print(
            f"  [red]✗ No tools discovered.[/red] "
            f"{'Check your token with /mcp auth ' + name if token else 'Set a token with /mcp auth ' + name}"
        )
        return

    table = Table(
        title=f"{name} — {len(tools)} tool(s) available",
        border_style="dim",
        expand=False,
        padding=(0, 2),
    )
    table.add_column("Tool", style=f"bold {TEAL}", width=32)
    table.add_column("Description", style="dim")

    for t in tools:
        fn = t.get("function", t)
        tool_name = fn.get("name", "?")
        desc = fn.get("description", "")[:70]
        table.add_row(tool_name, desc)

    console.print(table)
    console.print(
        f"\n  [{TEAL}]✓ {name} is working.[/] "
        f"Tools available as [dim]mcp_{name}_<tool>[/dim] in the agent."
    )


def _safe_call(fn: object, *args: object) -> None:
    """Call a function, catching SystemExit (raised by typer.Exit) gracefully."""
    try:
        fn(*args)  # type: ignore[operator]
    except SystemExit:
        pass  # typer.Exit — error already printed by the callee
    except Exception as e:
        console.print(f"  [red]Error:[/red] {e}")


def _run_search(query: str, api_key: str, x: bool) -> None:
    from grokcode.cli.search import _print_results
    from grokcode.search.search import web_search, x_search

    async def _do() -> None:
        label = "X" if x else "web"
        with console.status(f"[{TEAL}]Searching {label}: {query}[/]"):
            fn = x_search if x else web_search
            results = await fn(query=query, api_key=api_key, max_results=5)
        title = f'{"X" if x else "Web"} Search: "{query}"'
        _print_results(results, title=title)

    try:
        asyncio.run(_do())
    except Exception as e:
        console.print(f"  [red]Search failed:[/red] {e}")


def run_repl(config: AppConfig, api_key: str) -> None:
    """Interactive REPL — show welcome screen then loop until /exit."""
    username = getpass.getuser()
    show_welcome(config, username)

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print(f"\n  [{TEAL}]Goodbye![/]")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        if cmd in ("/exit", "/quit", "exit", "quit"):
            console.print(f"  [{TEAL}]Goodbye![/]")
            break

        elif cmd == "/help":
            _print_help()

        elif cmd == "/init":
            _init_grokcode_md()

        elif cmd == "/sessions":
            _show_sessions()

        elif cmd.startswith("/session export "):
            name = user_input[len("/session export ") :].strip()
            _safe_call(_session_export, name)

        elif cmd.startswith("/session import "):
            name = user_input[len("/session import ") :].strip()
            _safe_call(_session_import, name)

        elif cmd == "/workspace":
            _show_workspace(config)

        elif cmd == "/workspace list":
            _safe_call(_workspace_list_cmd)

        elif cmd.startswith("/workspace init "):
            name = user_input[len("/workspace init ") :].strip()
            _safe_call(_workspace_init_cmd, name)

        elif cmd.startswith("/workspace index "):
            paths = user_input[len("/workspace index ") :].strip()
            _safe_call(_workspace_index_cmd, paths)

        elif cmd in ("/mcp", "/mcp list"):
            _mcp_list(config)

        elif cmd == "/mcp catalog":
            _mcp_catalog(config)

        elif cmd.startswith("/mcp add "):
            parts = user_input[len("/mcp add ") :].strip().split(None, 1)
            if len(parts) == 2:
                _mcp_add(parts[0], parts[1], config)
            else:
                console.print("  [dim]Usage:[/dim] /mcp add <name> <url>")

        elif cmd.startswith("/mcp remove "):
            name = user_input[len("/mcp remove ") :].strip()
            _mcp_remove(name, config)

        elif cmd.startswith("/mcp auth "):
            name = user_input[len("/mcp auth ") :].strip()
            _mcp_auth(name, config)

        elif cmd.startswith("/mcp test "):
            name = user_input[len("/mcp test ") :].strip()
            _mcp_test(name, config)

        elif cmd in ("/config model", "/config model "):
            _select_model(config)

        elif cmd == "/config":
            _safe_call(_show_config)

        elif cmd.startswith("/config set "):
            parts = user_input[len("/config set ") :].strip().split(None, 1)
            if len(parts) == 2:
                _safe_call(_config_set_cmd, parts[0], parts[1])
            else:
                console.print("  [dim]Usage:[/dim] /config set <key> <value>")

        elif cmd == "/resume":
            try:
                asyncio.run(_execute_task("", api_key, config, resume=True))
            except KeyboardInterrupt:
                console.print("\n  [dim]Interrupted.[/dim]")

        elif cmd.startswith("/resume "):
            sid = user_input[len("/resume ") :].strip()
            try:
                asyncio.run(_execute_task("", api_key, config, session_id=sid))
            except KeyboardInterrupt:
                console.print("\n  [dim]Interrupted.[/dim]")

        elif cmd.startswith("/search "):
            query = user_input[len("/search ") :].strip()
            _run_search(query, api_key, x=False)

        elif cmd.startswith("/xsearch "):
            query = user_input[len("/xsearch ") :].strip()
            _run_search(query, api_key, x=True)

        elif cmd.startswith("/multi-agent "):
            task = user_input[len("/multi-agent ") :].strip()
            try:
                asyncio.run(_execute_task(task, api_key, config, multi_agent=True))
            except KeyboardInterrupt:
                console.print("\n  [dim]Interrupted.[/dim]")

        elif cmd.startswith("/dry-run "):
            task = user_input[len("/dry-run ") :].strip()
            try:
                asyncio.run(_execute_task(task, api_key, config, dry_run=True))
            except KeyboardInterrupt:
                console.print("\n  [dim]Interrupted.[/dim]")

        elif cmd == "/onboard" or cmd.startswith("/onboard "):
            args = user_input[len("/onboard") :].split()
            try:
                asyncio.run(_handle_onboard(args, config, api_key))
            except KeyboardInterrupt:
                console.print("\n  [dim]Interrupted.[/dim]")

        else:
            try:
                asyncio.run(_execute_task(user_input, api_key, config))
            except KeyboardInterrupt:
                console.print(
                    "\n  [dim]Interrupted — session saved. Type[/dim] /resume [dim]to continue.[/dim]"
                )


async def _execute_task(
    task: str,
    api_key: str,
    config: AppConfig,
    resume: bool = False,
    session_id: str | None = None,
    multi_agent: bool = False,
    dry_run: bool = False,
) -> None:
    """Delegate to the main agent runner."""
    # Late import avoids circular dependency with main.py
    from grokcode.cli.main import _run_task

    await _run_task(
        task=task,
        resume=resume,
        multi_agent=multi_agent,
        max_agents=5,
        auto_confirm=config.auto_confirm,
        debug=False,
        dry_run=dry_run,
        session_id=session_id,
    )


async def _handle_onboard(args: list[str], config: AppConfig, api_key: str) -> None:
    """Delegate to the onboard command handler."""
    from grokcode.repl.commands.onboard import handle_onboard

    await handle_onboard(args, config, api_key)
