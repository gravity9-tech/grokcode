from __future__ import annotations

"""
Integration tests for session export/import (handoff) flow.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from grokcode.agent.types import Message
from grokcode.session.handoff import HandoffBundle, export_session, import_session
from grokcode.session.session import Session, save_session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(task: str, files: list[str] | None = None) -> Session:
    session = Session.new(task=task)
    session.status = "done"
    session.history = [
        Message(role="user", content=task),
        Message(role="assistant", content="I'll implement that now."),
    ]
    session.files_modified = files or []
    return session


# ---------------------------------------------------------------------------
# export_session
# ---------------------------------------------------------------------------


async def test_export_session_creates_bundle(tmp_path: Path) -> None:
    # Create a real file to snapshot
    src_file = tmp_path / "src" / "auth.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text("def login(): pass\n")

    sessions_dir = tmp_path / "sessions"
    handoffs_dir = tmp_path / "handoffs"

    session = _make_session("Add JWT auth", files=[str(src_file)])
    await save_session(session, sessions_dir=sessions_dir)

    bundle = await export_session(
        session_id=session.id,
        name="jwt-feature",
        sessions_dir=sessions_dir,
        handoffs_dir=handoffs_dir,
    )

    assert bundle.name == "jwt-feature"
    assert bundle.session.id == session.id
    assert str(src_file) in bundle.files_snapshot
    assert "def login" in bundle.files_snapshot[str(src_file)]
    assert (handoffs_dir / "jwt-feature.json").exists()


async def test_export_session_uses_last_when_no_id(tmp_path: Path) -> None:
    from datetime import datetime

    sessions_dir = tmp_path / "sessions"
    handoffs_dir = tmp_path / "handoffs"

    s1 = _make_session("Old task")
    s1.started_at = datetime(2026, 1, 1)
    s2 = _make_session("New task")
    s2.started_at = datetime(2026, 3, 1)

    await save_session(s1, sessions_dir=sessions_dir)
    await save_session(s2, sessions_dir=sessions_dir)

    with (
        patch("grokcode.session.handoff.HANDOFFS_DIR", handoffs_dir),
        patch("grokcode.session.handoff.get_last_session", return_value=s2),
    ):
        bundle = await export_session(session_id=None, name="latest")

    assert bundle.session.task == "New task"


async def test_export_session_handles_missing_file(tmp_path: Path) -> None:
    """Files that no longer exist are skipped — no error raised."""
    sessions_dir = tmp_path / "sessions"
    handoffs_dir = tmp_path / "handoffs"

    session = _make_session("task", files=["/tmp/nonexistent_xyz_abc.py"])
    await save_session(session, sessions_dir=sessions_dir)

    bundle = await export_session(
        session_id=session.id,
        name="test-bundle",
        sessions_dir=sessions_dir,
        handoffs_dir=handoffs_dir,
    )

    # Missing file silently excluded from snapshot
    assert "/tmp/nonexistent_xyz_abc.py" not in bundle.files_snapshot


# ---------------------------------------------------------------------------
# import_session
# ---------------------------------------------------------------------------


async def test_import_session_restores_history(tmp_path: Path) -> None:
    handoffs_dir = tmp_path / "handoffs"
    handoffs_dir.mkdir(parents=True)

    original = _make_session("Refactor auth module")
    original.files_modified = ["src/auth.py"]

    bundle = HandoffBundle(name="auth-refactor", session=original, files_snapshot={})
    bundle_path = handoffs_dir / "auth-refactor.json"
    bundle_path.write_text(bundle.model_dump_json())

    imported = await import_session(name="auth-refactor", handoffs_dir=handoffs_dir)

    assert imported.id == original.id
    assert imported.task == "Refactor auth module"
    assert len(imported.history) == 2
    assert imported.history[0].role == "user"
    assert imported.history[1].role == "assistant"


async def test_import_session_not_found(tmp_path: Path) -> None:
    handoffs_dir = tmp_path / "handoffs"
    handoffs_dir.mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="nonexistent"):
        await import_session(name="nonexistent", handoffs_dir=handoffs_dir)


# ---------------------------------------------------------------------------
# Round-trip: export → import
# ---------------------------------------------------------------------------


async def test_export_import_roundtrip(tmp_path: Path) -> None:
    """Full roundtrip: export a session, import it, verify history is intact."""
    src_file = tmp_path / "app.py"
    src_file.write_text("def run(): pass\n")

    sessions_dir = tmp_path / "sessions"
    handoffs_dir = tmp_path / "handoffs"

    session = _make_session("Add logging to app.py", files=[str(src_file)])
    session.history.append(
        Message(role="assistant", content="Added structlog to app.py")
    )
    await save_session(session, sessions_dir=sessions_dir)

    await export_session(
        session_id=session.id,
        name="logging-feature",
        sessions_dir=sessions_dir,
        handoffs_dir=handoffs_dir,
    )
    imported = await import_session(name="logging-feature", handoffs_dir=handoffs_dir)

    assert imported.id == session.id
    assert len(imported.history) == 3  # user + 2 assistant messages
    assert imported.files_modified == [str(src_file)]
