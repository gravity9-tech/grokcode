from __future__ import annotations

import asyncio
import logging
import re
import shlex
from pathlib import Path

from pydantic import BaseModel

from grokcode.utils.ui import confirm, console

logger = logging.getLogger(__name__)

SAFE_PREFIXES = {
    "pytest",
    "python",
    "pip",
    "cat",
    "ls",
    "git",
    "echo",
    "find",
    "grep",
    "rg",
    "uv",
    "uvicorn",
    "mypy",
    "ruff",
    "make",
    "cargo",
    "go",
    "node",
    "npm",
    "yarn",
    "pnpm",
}

BLOCKLIST_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"sudo\s+rm",
    r":\(\)\s*\{",  # fork bomb
    r">\s*/dev/sda",  # disk overwrite
    r"mkfs\.",  # format disk
]

_BLOCKLIST_RE = re.compile("|".join(BLOCKLIST_PATTERNS))


class BashResult(BaseModel):
    stdout: str
    stderr: str
    exit_code: int

    def __str__(self) -> str:
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(f"[stderr] {self.stderr}")
        parts.append(f"[exit code: {self.exit_code}]")
        return "\n".join(parts)


class ToolError(Exception):
    pass


class BashTool:
    def __init__(self, auto_confirm: bool = False) -> None:
        self._cwd = Path.cwd()
        self.auto_confirm = auto_confirm

    async def execute(
        self,
        command: str,
        timeout: int = 30,
        auto_confirm: bool | None = None,
    ) -> BashResult:
        """Execute a shell command, streaming output to the terminal."""
        auto = auto_confirm if auto_confirm is not None else self.auto_confirm

        # Blocklist check
        if _BLOCKLIST_RE.search(command):
            raise ToolError(f"Blocked command (matches security blocklist): {command!r}")

        # Handle `cd` specially — update internal cwd
        stripped = command.strip()
        if stripped.startswith("cd "):
            target = stripped[3:].strip().strip('"').strip("'")
            new_path = (self._cwd / target).resolve()
            if new_path.is_dir():
                self._cwd = new_path
                return BashResult(stdout=str(self._cwd), stderr="", exit_code=0)
            return BashResult(stdout="", stderr=f"cd: {target}: No such directory", exit_code=1)

        # Confirmation gate for non-safe commands
        try:
            first_word = shlex.split(command)[0] if command.strip() else ""
        except ValueError:
            first_word = command.split()[0] if command.split() else ""

        if first_word not in SAFE_PREFIXES:
            approved = confirm(f"Run command: [bold]{command}[/bold]", auto=auto)
            if not approved:
                return BashResult(stdout="", stderr="Command not confirmed by user.", exit_code=1)

        # Execute
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._cwd,
        )

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        async def stream_stdout() -> None:
            assert proc.stdout is not None
            async for line in proc.stdout:
                decoded = line.decode(errors="replace").rstrip()
                stdout_lines.append(decoded)
                console.print(f"  [dim]{decoded}[/dim]")

        async def stream_stderr() -> None:
            assert proc.stderr is not None
            async for line in proc.stderr:
                decoded = line.decode(errors="replace").rstrip()
                stderr_lines.append(decoded)

        try:
            await asyncio.wait_for(
                asyncio.gather(stream_stdout(), stream_stderr()),
                timeout=timeout,
            )
            await proc.wait()
        except TimeoutError:
            proc.kill()
            raise ToolError(f"Command timed out after {timeout}s: {command!r}") from None

        return BashResult(
            stdout="\n".join(stdout_lines),
            stderr="\n".join(stderr_lines),
            exit_code=proc.returncode or 0,
        )
