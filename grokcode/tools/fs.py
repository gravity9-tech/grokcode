from __future__ import annotations

import os
from pathlib import Path

import aiofiles

from grokcode.utils.ui import confirm

MAX_FILE_SIZE = 100 * 1024  # 100 KB


class ToolError(Exception):
    pass


async def read_file(path: str) -> str:
    """Read a single file and return its contents."""
    p = Path(path)
    if not p.exists():
        raise ToolError(f"File not found: {path}")
    if p.stat().st_size > MAX_FILE_SIZE:
        raise ToolError(f"File too large (>{MAX_FILE_SIZE // 1024}KB): {path}")
    async with aiofiles.open(p, "r", errors="replace") as f:
        return await f.read()


async def read_directory(path: str, recursive: bool = False) -> str:
    """Return a tree-formatted directory listing."""
    p = Path(path)
    if not p.exists():
        return f"(Directory does not exist yet: {path})"
    if not p.is_dir():
        raise ToolError(f"Not a directory: {path}")

    lines: list[str] = [str(p) + "/"]
    entries = list(p.rglob("*")) if recursive else list(p.iterdir())
    entries = sorted(entries, key=lambda x: (x.is_file(), str(x)))

    for entry in entries:
        relative = entry.relative_to(p)
        depth = len(relative.parts) - 1
        indent = "  " * depth
        prefix = "├── "
        suffix = "/" if entry.is_dir() else ""
        lines.append(f"{indent}{prefix}{entry.name}{suffix}")

    return "\n".join(lines)


async def write_file(path: str, content: str, auto_confirm: bool = False) -> str:
    """Create or overwrite a file."""
    p = Path(path)
    if p.exists():
        approved = confirm(f"Overwrite existing file: {path}?", auto=auto_confirm)
        if not approved:
            return f"Skipped: {path}"

    p.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(p, "w") as f:
        await f.write(content)
    lines = content.count("\n") + 1
    return f"Written: {path} ({lines} lines)"


async def edit_file(path: str, old_str: str, new_str: str) -> str:
    """Replace exactly one occurrence of old_str with new_str in a file."""
    p = Path(path)
    if not p.exists():
        raise ToolError(
            f"File not found: {path}. Use write_file to create new files."
        )

    async with aiofiles.open(p, "r", errors="replace") as f:
        content = await f.read()

    count = content.count(old_str)
    if count == 0:
        raise ToolError(
            f"old_str not found in {path}. "
            "Make sure the string matches exactly (including whitespace). "
            "Use read_file to inspect the current file contents first."
        )
    if count > 1:
        match_line_numbers: list[int] = []
        pos = 0
        for _ in range(count):
            idx = content.find(old_str, pos)
            if idx == -1:
                break
            match_line_numbers.append(content[:idx].count("\n") + 1)
            pos = idx + 1
        lines_str = ", ".join(f"L{n}" for n in match_line_numbers)
        raise ToolError(
            f"old_str found {count} times in {path} at lines {lines_str}. "
            "Expand old_str to include more surrounding context (extra lines above/below) "
            "to make it unique, then retry."
        )

    new_content = content.replace(old_str, new_str, 1)
    async with aiofiles.open(p, "w") as f:
        await f.write(new_content)

    old_lines = old_str.count("\n") + 1
    new_lines = new_str.count("\n") + 1
    return f"Edited: {path} ({old_lines} lines → {new_lines} lines)"


async def delete_file(path: str, auto_confirm: bool = False) -> str:
    """Delete a file (always requires confirmation)."""
    p = Path(path)
    if not p.exists():
        raise ToolError(f"File not found: {path}")

    approved = confirm(f"Delete file: {path}?", auto=auto_confirm)
    if not approved:
        return f"Skipped: {path}"

    os.remove(p)
    return f"Deleted: {path}"


# ---------------------------------------------------------------------------
# OpenAI-compatible tool schemas
# ---------------------------------------------------------------------------

FS_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_directory",
            "description": "List a directory's contents as a tree.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to recurse into subdirectories",
                        "default": False,
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create a new file or overwrite an existing file with the given content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Full file content"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Replace exactly one occurrence of old_str with new_str in a file. "
                "old_str must match exactly one location — be specific."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "old_str": {
                        "type": "string",
                        "description": "Exact string to find and replace (must be unique in the file)",
                    },
                    "new_str": {"type": "string", "description": "Replacement string"},
                },
                "required": ["path", "old_str", "new_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file. Will ask for confirmation unless auto_confirm is set.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to delete"},
                },
                "required": ["path"],
            },
        },
    },
]
