from __future__ import annotations

from grokcode.tools.bash import BashTool
from grokcode.utils.ui import confirm


async def git_status(bash: BashTool) -> str:
    result = await bash.execute("git status", auto_confirm=True)
    return str(result)


async def git_diff(bash: BashTool, path: str | None = None) -> str:
    cmd = f"git diff {path}" if path else "git diff"
    result = await bash.execute(cmd, auto_confirm=True)
    return str(result)


async def git_add(bash: BashTool, paths: list[str]) -> str:
    joined = " ".join(f'"{p}"' for p in paths)
    result = await bash.execute(f"git add {joined}", auto_confirm=True)
    return str(result)


async def git_commit(bash: BashTool, message: str, auto_confirm: bool = False) -> str:
    approved = confirm(f"Commit with message: {message!r}?", auto=auto_confirm)
    if not approved:
        return "Commit cancelled by user."
    result = await bash.execute(f'git commit -m "{message}"', auto_confirm=True)
    return str(result)


async def git_log(bash: BashTool, n: int = 10) -> str:
    result = await bash.execute(f"git log --oneline -n {n}", auto_confirm=True)
    return str(result)


async def git_create_branch(bash: BashTool, name: str) -> str:
    result = await bash.execute(f"git checkout -b {name}", auto_confirm=True)
    return str(result)


# ---------------------------------------------------------------------------
# OpenAI-compatible tool schemas
# ---------------------------------------------------------------------------

GIT_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Show the current git working tree status.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Show git diff for the working tree or a specific file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Optional file path to diff"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_add",
            "description": "Stage files for commit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of file paths to stage",
                    },
                },
                "required": ["paths"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Commit staged changes with a message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message"},
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "Show recent git commit history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "n": {
                        "type": "integer",
                        "description": "Number of commits to show",
                        "default": 10,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_create_branch",
            "description": "Create and checkout a new git branch.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Branch name"},
                },
                "required": ["name"],
            },
        },
    },
]
