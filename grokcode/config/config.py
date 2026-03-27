from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

USER_CONFIG_DIR = Path.home() / ".grokcode"
USER_CONFIG_PATH = USER_CONFIG_DIR / "config.json"
WORKSPACE_CONFIG_FILENAME = "grokcode.workspace.json"


class UserConfig(BaseModel):
    xai_api_key: str | None = None
    model: str = "grok-3-mini"
    max_tokens: int = 8192
    auto_confirm: bool = False
    theme: str = "dark"


class McpServer(BaseModel):
    name: str
    url: str


class WorkspaceConfig(BaseModel):
    workspace: str
    collection_id: str = ""
    team_id: str = "default"
    rules: list[str] = Field(default_factory=list)
    mcp_servers: list[McpServer] = Field(default_factory=list)


class AppConfig(BaseModel):
    xai_api_key: str | None = None
    model: str = "grok-3-mini"
    max_tokens: int = 8192
    auto_confirm: bool = False
    theme: str = "dark"
    workspace_config: WorkspaceConfig | None = None


def load_user_config() -> UserConfig:
    """Read ~/.grokcode/config.json; create with defaults if missing."""
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not USER_CONFIG_PATH.exists():
        config = UserConfig()
        save_user_config(config)
        return config
    try:
        data = json.loads(USER_CONFIG_PATH.read_text())
        return UserConfig(**data)
    except (json.JSONDecodeError, Exception):
        return UserConfig()


def load_workspace_config() -> WorkspaceConfig | None:
    """Read ./grokcode.workspace.json if present."""
    path = Path.cwd() / WORKSPACE_CONFIG_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return WorkspaceConfig(**data)
    except (json.JSONDecodeError, Exception):
        return None


def get_config() -> AppConfig:
    """Merge user config + workspace config. Workspace rules take precedence."""
    user = load_user_config()
    workspace = load_workspace_config()

    return AppConfig(
        xai_api_key=user.xai_api_key,
        model=user.model,
        max_tokens=user.max_tokens,
        auto_confirm=user.auto_confirm,
        theme=user.theme,
        workspace_config=workspace,
    )


def save_user_config(config: UserConfig) -> None:
    """Write UserConfig back to ~/.grokcode/config.json."""
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    USER_CONFIG_PATH.write_text(config.model_dump_json(indent=2))
