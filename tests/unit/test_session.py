from __future__ import annotations

from pathlib import Path

import pytest

from grokcode.session.session import Session, get_last_session, list_sessions, load_session, save_session


async def test_save_and_load_session(tmp_path: Path) -> None:
    session = Session.new(task="Write a fibonacci function")
    await save_session(session, sessions_dir=tmp_path)

    loaded = await load_session(session.id, sessions_dir=tmp_path)
    assert loaded.id == session.id
    assert loaded.task == "Write a fibonacci function"
    assert loaded.status == "active"


async def test_list_sessions_empty(tmp_path: Path) -> None:
    sessions = await list_sessions(sessions_dir=tmp_path)
    assert sessions == []


async def test_list_sessions_sorted_newest_first(tmp_path: Path) -> None:
    from datetime import datetime, timedelta

    s1 = Session.new(task="Task 1")
    s1.started_at = datetime(2026, 3, 1, 10, 0)
    s2 = Session.new(task="Task 2")
    s2.started_at = datetime(2026, 3, 2, 10, 0)

    await save_session(s1, sessions_dir=tmp_path)
    await save_session(s2, sessions_dir=tmp_path)

    sessions = await list_sessions(sessions_dir=tmp_path)
    assert sessions[0].task == "Task 2"
    assert sessions[1].task == "Task 1"


async def test_get_last_session_none_when_empty(tmp_path: Path) -> None:
    result = await get_last_session(sessions_dir=tmp_path)
    assert result is None


async def test_get_last_session(tmp_path: Path) -> None:
    from datetime import datetime

    s1 = Session.new(task="Old task")
    s1.started_at = datetime(2026, 1, 1)
    s2 = Session.new(task="New task")
    s2.started_at = datetime(2026, 3, 1)

    await save_session(s1, sessions_dir=tmp_path)
    await save_session(s2, sessions_dir=tmp_path)

    last = await get_last_session(sessions_dir=tmp_path)
    assert last is not None
    assert last.task == "New task"


async def test_load_session_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await load_session("nonexistent-id", sessions_dir=tmp_path)
