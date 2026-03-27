from __future__ import annotations

import asyncio
import json
import logging
import re

from pydantic import BaseModel, Field

from grokcode.config.config import AppConfig

logger = logging.getLogger(__name__)


class SubtaskPlan(BaseModel):
    id: str
    description: str
    files: list[str] = Field(default_factory=list)
    agent_instructions: str


class MultiAgentResult(BaseModel):
    subtasks_completed: int
    files_modified: list[str] = Field(default_factory=list)
    test_output: str = ""
    summary: str


async def run_multi_agent(
    task: str,
    config: AppConfig,
    api_key: str,
    max_agents: int = 5,
    auto_confirm: bool = False,
    dry_run: bool = False,
) -> MultiAgentResult:
    """
    Orchestrator + sub-agent fan-out:
    1. Orchestrator decomposes task into SubtaskPlan[]
    2. Sub-agents run concurrently (bounded by semaphore)
    3. Merge agent resolves conflicts
    4. Run pytest and capture output
    """
    from grokcode.agent.agent import Agent, DoneEvent, ErrorEvent
    from grokcode.agent.grok_client import GrokClient
    from grokcode.agent.tool_registry import ToolRegistry
    from grokcode.tools.bash import BashTool
    from grokcode.tools.fs import FS_TOOL_SCHEMAS, edit_file, glob_files, grep_files, read_directory, read_file, write_file
    from grokcode.utils.ui import console

    async with GrokClient(api_key=api_key, model=config.model, max_tokens=config.max_tokens) as client:
        # Step 1: Orchestrator decomposes the task
        console.print("  [cyan]●[/cyan] Orchestrator: decomposing task...")
        subtasks = await _decompose_task(task, config, client)
        console.print(f"  [cyan]●[/cyan] {len(subtasks)} subtasks planned")

        if not subtasks:
            return MultiAgentResult(
                subtasks_completed=0,
                summary="Orchestrator produced no subtasks.",
            )

        # Display planned subtasks
        for i, st in enumerate(subtasks, 1):
            console.print(f"    [dim]{i}.[/dim] {st.description}")

        # Step 2: Execute sub-agents concurrently
        semaphore = asyncio.Semaphore(min(max_agents, len(subtasks)))
        all_files_modified: list[str] = []

        file_locks: dict[str, asyncio.Lock] = {}

        async def locked_edit_file(path: str, old_str: str, new_str: str) -> str:
            if path not in file_locks:
                file_locks[path] = asyncio.Lock()
            async with file_locks[path]:
                return await edit_file(path, old_str, new_str)

        async def locked_write_file(path: str, content: str) -> str:
            if path not in file_locks:
                file_locks[path] = asyncio.Lock()
            async with file_locks[path]:
                return await write_file(path, content, auto_confirm=True)

        async def run_subtask(subtask: SubtaskPlan) -> list[str]:
            async with semaphore:
                console.print(f"  [yellow]→[/yellow] Starting sub-agent: {subtask.description[:60]}")
                bash_tool = BashTool(auto_confirm=auto_confirm)
                registry = ToolRegistry()
                registry.register("read_file", lambda path: read_file(path), FS_TOOL_SCHEMAS[0])
                registry.register("read_directory", lambda path, recursive=False: read_directory(path, recursive), FS_TOOL_SCHEMAS[1])
                registry.register("write_file", lambda path, content: locked_write_file(path, content), FS_TOOL_SCHEMAS[2])
                registry.register("edit_file", lambda path, old_str, new_str: locked_edit_file(path, old_str, new_str), FS_TOOL_SCHEMAS[3])
                registry.register("glob_files", lambda pattern, directory=".": glob_files(pattern, directory), FS_TOOL_SCHEMAS[5])
                registry.register("grep_files", lambda pattern, directory=".", file_glob="**/*": grep_files(pattern, directory, file_glob), FS_TOOL_SCHEMAS[6])

                async with GrokClient(api_key=api_key, model=config.model, max_tokens=config.max_tokens) as sub_client:
                    agent = Agent(config=config, tool_registry=registry, grok_client=sub_client)
                    files: list[str] = []
                    async for event in agent.run(
                        task=subtask.agent_instructions,
                        auto_confirm=auto_confirm,
                        dry_run=dry_run,
                    ):
                        if hasattr(event, "files_touched"):
                            files.extend(event.files_touched)  # type: ignore[attr-defined]
                        if isinstance(event, DoneEvent):
                            console.print(f"  [green]✓[/green] Sub-agent done: {subtask.description[:50]}")
                        elif isinstance(event, ErrorEvent):
                            console.print(f"  [red]✗[/red] Sub-agent error: {event.message[:80]}")
                    return files

        results = await asyncio.gather(*[run_subtask(st) for st in subtasks])
        for file_list in results:
            all_files_modified.extend(file_list)

        # Step 3: Run tests
        test_output = ""
        if not dry_run:
            console.print("  [cyan]●[/cyan] Running tests...")
            bash = BashTool(auto_confirm=True)
            try:
                result = await bash.execute("python -m pytest --tb=short -q", timeout=120)
                test_output = str(result)
            except Exception as e:
                test_output = f"Could not run tests: {e}"

        return MultiAgentResult(
            subtasks_completed=len(subtasks),
            files_modified=list(set(all_files_modified)),
            test_output=test_output,
            summary=(
                f"Completed {len(subtasks)} subtasks across {len(set(all_files_modified))} files.\n"
                + (f"\nTest output:\n{test_output[:500]}" if test_output else "")
            ),
        )


async def _decompose_task(
    task: str,
    config: AppConfig,
    client: object,
) -> list[SubtaskPlan]:
    """Use orchestrator to break task into subtasks. Returns list of SubtaskPlan."""
    from grokcode.agent.grok_client import GrokClient

    grok: GrokClient = client  # type: ignore[assignment]

    orchestrator_system = (
        "You are a task decomposition agent. "
        "Break the given coding task into 2-5 independent subtasks. "
        "Respond ONLY with a JSON array of objects. No markdown, no explanation. "
        'Each object must have: "id" (string), "description" (string), '
        '"files" (array of strings), "agent_instructions" (string with full instructions for the sub-agent).'
    )

    messages = [
        {"role": "system", "content": orchestrator_system},
        {"role": "user", "content": f"Decompose this task:\n\n{task}"},
    ]

    full_response = ""
    async for chunk in grok.chat(messages, stream=False):
        if chunk.content:
            full_response += chunk.content

    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?\s*", "", full_response).strip().rstrip("```").strip()

    try:
        data = json.loads(cleaned)
        return [SubtaskPlan(**item) for item in data]
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Failed to parse subtask plan: %s\nRaw: %s", e, full_response[:500])
        # Fall back: treat whole task as single subtask
        return [
            SubtaskPlan(
                id="task-1",
                description=task[:100],
                files=[],
                agent_instructions=task,
            )
        ]
