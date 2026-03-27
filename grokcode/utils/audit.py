from __future__ import annotations

from datetime import datetime
from pathlib import Path

import aiofiles
from pydantic import BaseModel

AUDIT_LOG_PATH = Path.home() / ".grokcode" / "audit.log"


class AuditEntry(BaseModel):
    timestamp: datetime
    session_id: str
    tool: str
    args_summary: str
    result_summary: str


async def log_action(entry: AuditEntry) -> None:
    """Append an audit entry to the audit log file."""
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = entry.model_dump_json() + "\n"
    async with aiofiles.open(AUDIT_LOG_PATH, "a") as f:
        await f.write(line)
