from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from grokcode.utils.audit import AUDIT_LOG_PATH, AuditEntry, log_action


async def test_log_action_appends_to_file(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.log"

    with patch("grokcode.utils.audit.AUDIT_LOG_PATH", log_path):
        entry = AuditEntry(
            timestamp=datetime(2026, 3, 27, 10, 0, 0),
            session_id="sess-abc",
            tool="read_file",
            args_summary="path='main.py'",
            result_summary="def foo(): ...",
        )
        await log_action(entry)

    assert log_path.exists()
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["tool"] == "read_file"
    assert data["session_id"] == "sess-abc"


async def test_log_action_appends_multiple_entries(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.log"

    with patch("grokcode.utils.audit.AUDIT_LOG_PATH", log_path):
        for i in range(3):
            await log_action(
                AuditEntry(
                    timestamp=datetime.now(),
                    session_id="sess-xyz",
                    tool=f"tool_{i}",
                    args_summary="",
                    result_summary="ok",
                )
            )

    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 3
    tools = [json.loads(l)["tool"] for l in lines]
    assert tools == ["tool_0", "tool_1", "tool_2"]
