from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from grokcode.agent.system_prompt import build_system_prompt
from grokcode.config.config import AppConfig, McpServer, WorkspaceConfig


def _make_config(**kwargs) -> AppConfig:
    return AppConfig(**kwargs)


def test_system_prompt_base_content() -> None:
    config = _make_config()
    prompt = build_system_prompt(config)
    assert "GrokCode" in prompt
    assert "Grok" in prompt
    assert "tools" in prompt.lower()


def test_system_prompt_includes_cwd() -> None:
    config = _make_config()
    import os
    prompt = build_system_prompt(config)
    assert os.getcwd() in prompt


def test_system_prompt_includes_git_branch() -> None:
    config = _make_config()
    prompt = build_system_prompt(config, git_branch="feature/auth-jwt")
    assert "feature/auth-jwt" in prompt


def test_system_prompt_includes_grokcode_md(tmp_path: Path) -> None:
    grokcode_md = tmp_path / "GROKCODE.md"
    grokcode_md.write_text("Always use async/await for I/O operations.")

    config = _make_config()
    with patch("pathlib.Path.cwd", return_value=tmp_path):
        prompt = build_system_prompt(config)

    assert "Always use async/await" in prompt
    assert "<project_instructions>" in prompt


def test_system_prompt_includes_team_rules() -> None:
    ws = WorkspaceConfig(
        workspace="test",
        collection_id="col-123",
        team_id="team-a",
        rules=[
            "Always use Python type hints",
            "Use Pydantic v2",
            "Never expose PII in logs",
        ],
    )
    config = _make_config(workspace_config=ws)
    prompt = build_system_prompt(config)

    assert "<team_rules>" in prompt
    assert "Always use Python type hints" in prompt
    assert "Use Pydantic v2" in prompt
    assert "Never expose PII in logs" in prompt


def test_system_prompt_no_team_rules_when_empty() -> None:
    ws = WorkspaceConfig(workspace="test", collection_id="col-123", team_id="team-a")
    config = _make_config(workspace_config=ws)
    prompt = build_system_prompt(config)
    assert "<team_rules>" not in prompt


def test_system_prompt_no_grokcode_md_when_absent(tmp_path: Path) -> None:
    config = _make_config()
    with patch("pathlib.Path.cwd", return_value=tmp_path):
        prompt = build_system_prompt(config)
    assert "<project_instructions>" not in prompt
