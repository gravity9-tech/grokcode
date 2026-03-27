from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

import aiofiles
from pydantic import BaseModel, Field

from grokcode.agent.types import Message, TokenUsage

DEFAULT_SESSIONS_DIR = Path.home() / ".grokcode" / "sessions"


class Session(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    task: str
    started_at: datetime = Field(default_factory=datetime.now)
    history: list[Message] = Field(default_factory=list)
    files_modified: list[str] = Field(default_factory=list)
    status: Literal["active", "done", "interrupted"] = "active"
    token_usage: TokenUsage | None = None

    @classmethod
    def new(cls, task: str) -> "Session":
        return cls(task=task)


async def save_session(
    session: Session,
    sessions_dir: Path = DEFAULT_SESSIONS_DIR,
) -> None:
    """Persist a session to disk as JSON."""
    sessions_dir.mkdir(parents=True, exist_ok=True)
    path = sessions_dir / f"{session.id}.json"
    async with aiofiles.open(path, "w") as f:
        await f.write(session.model_dump_json(indent=2))


async def load_session(
    session_id: str,
    sessions_dir: Path = DEFAULT_SESSIONS_DIR,
) -> Session:
    """Load a session by ID."""
    path = sessions_dir / f"{session_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Session not found: {session_id}")
    async with aiofiles.open(path, "r") as f:
        data = json.loads(await f.read())
    return Session(**data)


async def list_sessions(
    sessions_dir: Path = DEFAULT_SESSIONS_DIR,
) -> list[Session]:
    """Return all sessions sorted newest-first."""
    if not sessions_dir.exists():
        return []
    sessions = []
    for path in sessions_dir.glob("*.json"):
        try:
            async with aiofiles.open(path, "r") as f:
                data = json.loads(await f.read())
            sessions.append(Session(**data))
        except Exception:
            continue
    return sorted(sessions, key=lambda s: s.started_at, reverse=True)


async def get_last_session(
    sessions_dir: Path = DEFAULT_SESSIONS_DIR,
) -> Session | None:
    """Return the most recent session, or None if no sessions exist."""
    all_sessions = await list_sessions(sessions_dir)
    return all_sessions[0] if all_sessions else None
