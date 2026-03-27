from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from grokcode.workspace.workspace import (
    INDEXABLE_EXTENSIONS,
    _collect_files,
    _is_ignored,
    _load_index,
    _persist_doc_id,
    index_paths,
    init_workspace,
    load_workspace_index,
)


# ---------------------------------------------------------------------------
# File collection helpers
# ---------------------------------------------------------------------------


def test_collect_files_from_directory(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "README.md").write_text("# Hello")
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "util.py").write_text("pass")

    files = _collect_files([tmp_path])
    names = {f.name for f in files}
    assert "main.py" in names
    assert "README.md" in names
    assert "util.py" in names


def test_collect_files_ignores_hidden_dirs(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("git config")
    (tmp_path / "main.py").write_text("pass")

    files = _collect_files([tmp_path])
    paths = [str(f) for f in files]
    assert not any(".git" in p for p in paths)
    assert any("main.py" in p for p in paths)


def test_collect_files_ignores_venv(tmp_path: Path) -> None:
    venv = tmp_path / ".venv"
    venv.mkdir()
    (venv / "lib.py").write_text("pass")
    (tmp_path / "app.py").write_text("pass")

    files = _collect_files([tmp_path])
    paths = [str(f) for f in files]
    assert not any(".venv" in p for p in paths)


def test_is_ignored() -> None:
    assert _is_ignored(Path(".git/config"))
    assert _is_ignored(Path(".venv/lib/python3.11/site.py"))
    assert _is_ignored(Path("node_modules/pkg/index.js"))
    assert not _is_ignored(Path("src/main.py"))
    assert not _is_ignored(Path("docs/README.md"))


# ---------------------------------------------------------------------------
# Index persistence
# ---------------------------------------------------------------------------


def test_persist_and_load_index(tmp_path: Path) -> None:
    index_path = tmp_path / ".grokcode" / "workspace-index.json"

    with patch("grokcode.workspace.workspace.WORKSPACE_INDEX_PATH", index_path):
        _persist_doc_id(Path("src/main.py"), "doc-abc123")
        _persist_doc_id(Path("docs/README.md"), "doc-def456")

        index = _load_index()
        assert index["src/main.py"] == "doc-abc123"
        assert index["docs/README.md"] == "doc-def456"


# ---------------------------------------------------------------------------
# init_workspace
# ---------------------------------------------------------------------------


async def test_init_workspace_writes_config(tmp_path: Path) -> None:
    mock_client = AsyncMock()
    mock_collection = MagicMock()
    mock_collection.id = "vs_test123"
    mock_collection.name = "my-project"
    mock_client.create_collection = AsyncMock(return_value=mock_collection)

    config_path = tmp_path / "grokcode.workspace.json"

    with patch("pathlib.Path.cwd", return_value=tmp_path):
        result = await init_workspace(name="my-project", team_id="team-a", client=mock_client)

    assert result["collection_id"] == "vs_test123"
    assert result["workspace"] == "my-project"
    assert result["team_id"] == "team-a"
    assert config_path.exists()

    data = json.loads(config_path.read_text())
    assert data["collection_id"] == "vs_test123"


# ---------------------------------------------------------------------------
# index_paths
# ---------------------------------------------------------------------------


async def test_index_paths_uploads_eligible_files(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print('hi')")
    (tmp_path / "notes.md").write_text("# Notes")

    mock_client = AsyncMock()
    mock_doc = MagicMock()
    mock_doc.id = "doc-xyz"
    mock_client.upload_document = AsyncMock(return_value=mock_doc)

    index_path = tmp_path / ".grokcode" / "workspace-index.json"

    with patch("grokcode.workspace.workspace.WORKSPACE_INDEX_PATH", index_path):
        uploaded, skipped = await index_paths(
            paths=[tmp_path],
            collection_id="vs_test",
            client=mock_client,
        )

    assert len(uploaded) == 2
    assert len(skipped) == 0
    assert mock_client.upload_document.call_count == 2


async def test_index_paths_skips_oversized_files(tmp_path: Path) -> None:
    big_file = tmp_path / "big.py"
    big_file.write_bytes(b"x" * (101 * 1024))
    small_file = tmp_path / "small.py"
    small_file.write_text("pass")

    mock_client = AsyncMock()
    mock_doc = MagicMock()
    mock_doc.id = "doc-small"
    mock_client.upload_document = AsyncMock(return_value=mock_doc)

    index_path = tmp_path / ".grokcode" / "workspace-index.json"
    with patch("grokcode.workspace.workspace.WORKSPACE_INDEX_PATH", index_path):
        uploaded, skipped = await index_paths(
            paths=[tmp_path],
            collection_id="vs_test",
            client=mock_client,
        )

    assert len(uploaded) == 1
    assert len(skipped) == 1
    assert "too large" in skipped[0]
