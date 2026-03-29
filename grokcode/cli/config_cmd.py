from __future__ import annotations

from typing import Annotated

import typer
from rich.table import Table

from grokcode.config.config import (
    UserConfig,
    get_config,
    load_user_config,
    save_user_config,
)
from grokcode.config.keychain import set_api_key
from grokcode.utils.ui import console, print_error, print_success

config_app = typer.Typer(help="Manage GrokCode configuration.")

_SETTABLE_KEYS = {"xai_api_key", "model", "max_tokens", "auto_confirm", "theme"}


@config_app.command("set")
def config_set(
    key: Annotated[str, typer.Argument(help="Config key to set")],
    value: Annotated[str, typer.Argument(help="Value to assign")],
) -> None:
    """Set a configuration value."""
    if key not in _SETTABLE_KEYS:
        print_error(
            f"Unknown config key: [bold]{key}[/bold]\n"
            f"Valid keys: {', '.join(sorted(_SETTABLE_KEYS))}"
        )
        raise typer.Exit(1)

    user_config = load_user_config()

    # API key gets special treatment — store in keychain
    if key == "xai_api_key":
        try:
            set_api_key(value)
            print_success("API key stored securely in system keychain.")
        except RuntimeError as e:
            print_error(str(e))
            raise typer.Exit(1) from e
        # Also persist masked reference so config show works
        user_config.xai_api_key = value[:8] + "..." if len(value) > 8 else value
        save_user_config(user_config)
        return

    # Coerce value to the correct type
    field_info = UserConfig.model_fields.get(key)
    if field_info is None:
        print_error(f"Unknown config key: {key}")
        raise typer.Exit(1)

    annotation = field_info.annotation
    try:
        if annotation is bool or annotation == "bool":
            coerced = value.lower() in ("true", "1", "yes")
        elif annotation is int or annotation == "int":
            coerced = int(value)
        else:
            coerced = value
    except ValueError:
        print_error(f"Invalid value {value!r} for key {key!r}")
        raise typer.Exit(1) from None

    setattr(user_config, key, coerced)
    save_user_config(user_config)
    print_success(f"Config updated: [bold]{key}[/bold] = {coerced!r}")


@config_app.command("show")
def config_show() -> None:
    """Display current configuration."""
    config = get_config()

    table = Table(title="GrokCode Configuration", border_style="dim", expand=False)
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    table.add_column("Source", style="dim")

    # Mask API key
    api_key = config.xai_api_key or ""
    masked_key = (api_key[:8] + "...") if len(api_key) > 8 else (api_key or "[red]not set[/red]")

    table.add_row("xai_api_key", masked_key, "keychain / env")
    table.add_row("model", config.model, "user config")
    table.add_row("max_tokens", str(config.max_tokens), "user config")
    table.add_row("auto_confirm", str(config.auto_confirm), "user config")
    table.add_row("theme", config.theme, "user config")

    if config.workspace_config:
        ws = config.workspace_config
        table.add_row("workspace", ws.workspace, "grokcode.workspace.json")
        table.add_row("team_id", ws.team_id, "grokcode.workspace.json")
        table.add_row(
            "collection_id", ws.collection_id or "[dim]not set[/dim]", "grokcode.workspace.json"
        )
        table.add_row("rules count", str(len(ws.rules)), "grokcode.workspace.json")
        table.add_row("mcp_servers", str(len(ws.mcp_servers)), "grokcode.workspace.json")

    console.print(table)

    from grokcode.config.config import USER_CONFIG_DIR

    console.print(f"\n  [dim]Config dir:[/dim]  {USER_CONFIG_DIR}")
    console.print(f"  [dim]Audit log:[/dim]   {USER_CONFIG_DIR / 'audit.log'}")
