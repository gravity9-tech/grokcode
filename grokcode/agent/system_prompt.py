from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


def build_system_prompt(
    config: object,
    git_branch: str | None = None,
) -> str:
    """Build the full system prompt for the agent."""
    from grokcode.config.config import AppConfig

    cfg: AppConfig = config  # type: ignore[assignment]

    lines: list[str] = []

    lines.append(
        "You are GrokCode, an agentic coding assistant powered by xAI Grok. "
        "You help software engineers read, write, edit, and manage code in their terminal."
    )
    lines.append("")
    lines.append("## Capabilities")
    lines.append(
        "You have access to tools for reading/writing files, executing shell commands, "
        "running git operations, and searching the web. Use them autonomously to complete tasks."
    )
    lines.append("")
    lines.append("## Rules")
    lines.append("- Always read files before editing them to understand their current state.")
    lines.append("- Use edit_file for targeted changes; use write_file only to create new files.")
    lines.append("- Run tests after making changes whenever a test suite is available.")
    lines.append("- Request only the minimum permissions needed.")
    lines.append("- Never expose secrets, API keys, or PII in your output.")
    lines.append("- Be concise in your thinking; be precise in your tool calls.")
    lines.append("")

    # Runtime context
    lines.append("## Runtime Context")
    lines.append(f"- Date/time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Working directory: {os.getcwd()}")
    if git_branch:
        lines.append(f"- Git branch: {git_branch}")
    lines.append("")

    # GROKCODE.md project instructions
    grokcode_md = Path.cwd() / "GROKCODE.md"
    if grokcode_md.exists():
        try:
            content = grokcode_md.read_text()
            lines.append("<project_instructions>")
            lines.append(content.strip())
            lines.append("</project_instructions>")
            lines.append("")
        except OSError:
            pass

    # Team workspace rules
    if cfg.workspace_config and cfg.workspace_config.rules:
        lines.append("<team_rules>")
        for rule in cfg.workspace_config.rules:
            lines.append(f"- {rule}")
        lines.append("</team_rules>")
        lines.append("")

    return "\n".join(lines)
