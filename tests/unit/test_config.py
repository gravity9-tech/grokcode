from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from grokcode.config.config import (
    AppConfig,
    UserConfig,
    WorkspaceConfig,
    get_config,
    load_user_config,
    load_workspace_config,
    save_user_config,
)


@pytest.fixture
def tmp_home(tmp_path: Path) -> Path:
    """Fixture that patches home directory to a temp path."""
    return tmp_path


def test_user_config_defaults() -> None:
    config = UserConfig()
    assert config.model == "grok-3-mini"
    assert config.max_tokens == 8192
    assert config.auto_confirm is False
    assert config.theme == "dark"
    assert config.xai_api_key is None


def test_save_and_load_user_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config = UserConfig(model="grok-4", max_tokens=4096, auto_confirm=True)

    with (
        patch("grokcode.config.config.USER_CONFIG_DIR", tmp_path),
        patch("grokcode.config.config.USER_CONFIG_PATH", config_path),
    ):
        save_user_config(config)
        assert config_path.exists()

        loaded = load_user_config()
        assert loaded.model == "grok-4"
        assert loaded.max_tokens == 4096
        assert loaded.auto_confirm is True


def test_load_user_config_creates_defaults_when_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    with (
        patch("grokcode.config.config.USER_CONFIG_DIR", tmp_path),
        patch("grokcode.config.config.USER_CONFIG_PATH", config_path),
    ):
        config = load_user_config()
        assert config.model == "grok-3-mini"
        assert config_path.exists()


def test_load_workspace_config_missing(tmp_path: Path) -> None:
    with patch("grokcode.config.config.Path") as mock_path:
        # Simulate no workspace file
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = load_workspace_config()
            assert result is None


def test_workspace_config_model() -> None:
    ws = WorkspaceConfig(
        workspace="test-project",
        collection_id="col-abc123",
        team_id="myteam",
        rules=["Use type hints", "No PII in logs"],
        mcp_servers=[],
    )
    assert ws.workspace == "test-project"
    assert len(ws.rules) == 2


def test_get_config_merges_user_and_workspace(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    user = UserConfig(model="grok-4", xai_api_key="test-key")

    workspace_data = {
        "workspace": "my-project",
        "collection_id": "col-123",
        "team_id": "team-a",
        "rules": ["rule1"],
        "mcp_servers": [],
    }
    workspace_file = tmp_path / "grokcode.workspace.json"
    workspace_file.write_text(json.dumps(workspace_data))

    with (
        patch("grokcode.config.config.USER_CONFIG_DIR", tmp_path),
        patch("grokcode.config.config.USER_CONFIG_PATH", config_path),
        patch("pathlib.Path.cwd", return_value=tmp_path),
    ):
        save_user_config(user)
        config = get_config()
        assert config.model == "grok-4"
        assert config.workspace_config is not None
        assert config.workspace_config.workspace == "my-project"
        assert "rule1" in config.workspace_config.rules
