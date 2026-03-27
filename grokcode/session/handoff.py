from __future__ import annotations

import json
from pathlib import Path

import aiofiles
from pydantic import BaseModel

from grokcode.session.session import (
    DEFAULT_SESSIONS_DIR,
    Session,
    get_last_session,
    load_session,
)

HANDOFFS_DIR = Path(".grokcode") / "handoffs"


class HandoffBundle(BaseModel):
    name: str
    session: Session
    files_snapshot: dict[str, str]  # path -> content


async def export_session(
    session_id: str | None,
    name: str,
    sessions_dir: Path = DEFAULT_SESSIONS_DIR,
    handoffs_dir: Path = HANDOFFS_DIR,
) -> HandoffBundle:
    """Export a session with a snapshot of all modified files."""
    if session_id:
        session = await load_session(session_id, sessions_dir=sessions_dir)
    else:
        session = await get_last_session(sessions_dir=sessions_dir)
        if not session:
            raise RuntimeError("No sessions found to export.")

    # Snapshot modified files
    files_snapshot: dict[str, str] = {}
    for path in session.files_modified:
        try:
            async with aiofiles.open(path, "r", errors="replace") as f:
                files_snapshot[path] = await f.read()
        except OSError:
            pass  # file may have been deleted or moved

    bundle = HandoffBundle(name=name, session=session, files_snapshot=files_snapshot)

    handoffs_dir.mkdir(parents=True, exist_ok=True)
    out_path = handoffs_dir / f"{name}.json"
    async with aiofiles.open(out_path, "w") as f:
        await f.write(bundle.model_dump_json(indent=2))

    return bundle


async def import_session(
    name: str,
    handoffs_dir: Path = HANDOFFS_DIR,
) -> Session:
    """Load a HandoffBundle and return the embedded session."""
    path = handoffs_dir / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Handoff not found: {name}\nLooked in: {path.resolve()}"
        )

    async with aiofiles.open(path, "r") as f:
        data = json.loads(await f.read())

    bundle = HandoffBundle(**data)
    return bundle.session
