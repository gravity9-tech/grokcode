# GrokCode CLI — Implementation Todo List (Python)

> Pass this to Claude Code or Devin AI to implement.
> Each task is scoped to be completable independently. Work Phase 1 → 4 in order.
> The repo is a Python 3.11+ project using `typer`, `rich`, `httpx`, and `pydantic`.

---

## Phase 1: Project Foundation & Grok Integration

### 1.1 — Repo & Tooling Setup
- [ ] Initialize project with `pyproject.toml` (PEP 621):
  - Package name: `grokcode`
  - Python requires: `>=3.11`
  - Entry point: `grokcode = "grokcode.cli.main:app"`
- [ ] Add core dependencies to `[project.dependencies]` in `pyproject.toml`:
  - `typer[all]>=0.12` — CLI framework with auto-completion
  - `rich>=13` — terminal UI (spinners, tables, syntax highlighting, live progress)
  - `httpx>=0.27` — async HTTP with SSE streaming support
  - `pydantic>=2.0` — typed models for config, messages, sessions
  - `keyring>=24` — cross-platform secure keychain access
  - `keyrings.alt>=5` — fallback keyring for Linux servers without desktop keyring
  - `python-dotenv>=1.0` — `.env` file support
  - `aiofiles>=23` — async file I/O
- [ ] Add dev dependencies to `[project.optional-dependencies] dev`:
  - `pytest>=8`, `pytest-asyncio>=0.23`, `respx>=0.21` (mock httpx), `pytest-cov`
  - `ruff` — linting + formatting
  - `mypy` — type checking
- [ ] Create the following package structure:
  ```
  grokcode/
    cli/
      main.py        # typer app, top-level commands
      workspace.py   # workspace subcommands
      session.py     # session subcommands
      search.py      # search subcommands
      config_cmd.py  # config subcommands
    agent/
      agent.py       # core agent loop
      grok_client.py # xAI API client
      system_prompt.py
      tool_registry.py
      types.py
    tools/
      fs.py          # file system tools
      bash.py        # shell execution tool
      git.py         # git tools
    workspace/
      collections_client.py  # xAI Collections API
      workspace.py           # workspace business logic
    session/
      session.py     # session persistence
      handoff.py     # session export/import
    search/
      search.py      # web + X search wrappers
    config/
      config.py      # config loading + merging
      keychain.py    # keyring wrapper
    utils/
      audit.py       # audit logger
      ui.py          # rich UI helpers (spinners, confirms, diffs)
  tests/
  demo/
  ```
- [ ] Create `.gitignore` (include `.grokcode/`, `.env`, `dist/`, `__pycache__/`, `.mypy_cache/`)
- [ ] Set up `[tool.ruff]` in `pyproject.toml` for linting and formatting
- [ ] Set up `[tool.pytest.ini_options]` in `pyproject.toml`: `asyncio_mode = "auto"`
- [ ] Set up `[tool.mypy]` in `pyproject.toml`: `strict = true`

### 1.2 — Configuration System
- [ ] Create `grokcode/config/config.py`:
  - `class UserConfig(BaseModel)`: `xai_api_key: str | None`, `model: str = "grok-4"`, `max_tokens: int = 8192`, `auto_confirm: bool = False`, `theme: str = "dark"`
  - `class McpServer(BaseModel)`: `name: str`, `url: str`
  - `class WorkspaceConfig(BaseModel)`: `workspace: str`, `collection_id: str`, `team_id: str`, `rules: list[str]`, `mcp_servers: list[McpServer]`
  - `class AppConfig(BaseModel)`: merged view combining both configs
  - `def load_user_config() -> UserConfig` — read `~/.grokcode/config.json`; create with defaults if missing
  - `def load_workspace_config() -> WorkspaceConfig | None` — read `./grokcode.workspace.json` if present
  - `def get_config() -> AppConfig` — merge both; project-level overrides user-level
  - `def save_user_config(config: UserConfig)` — write back to `~/.grokcode/config.json`
- [ ] Create `grokcode/config/keychain.py`:
  - `def get_api_key() -> str | None` — try `keyring.get_password("grokcode", "xai_api_key")`; fall back to `XAI_API_KEY` env var
  - `def set_api_key(key: str)` — call `keyring.set_password("grokcode", "xai_api_key", key)`
- [ ] Implement `grokcode config set <key> <value>` command
- [ ] Implement `grokcode config show` command — `rich.table.Table` with key/value rows; mask API key to first 8 chars + `...`
- [ ] Write unit tests for config merging logic and default creation

### 1.3 — xAI / Grok API Client
- [ ] Create `grokcode/agent/types.py` with Pydantic models:
  - `class Message(BaseModel)`: `role: Literal["system","user","assistant","tool"]`, `content: str | list`
  - `class ToolDefinition(BaseModel)`: `name: str`, `description: str`, `parameters: dict`
  - `class ToolCall(BaseModel)`: `id: str`, `name: str`, `arguments: dict`
  - `class ToolResult(BaseModel)`: `tool_call_id: str`, `content: str`
  - `class TokenUsage(BaseModel)`: `input_tokens: int`, `output_tokens: int`
  - `class GrokResponse(BaseModel)`: `content: str | None`, `tool_calls: list[ToolCall]`, `usage: TokenUsage | None`
- [ ] Create `grokcode/agent/grok_client.py`:
  - `class GrokClient` holding an `httpx.AsyncClient` with `Authorization: Bearer {api_key}` header
  - `async def chat(messages, tools=None, stream=True, **kwargs) -> AsyncGenerator[GrokResponse, None]`
  - POST to `https://api.x.ai/v1/chat/completions` with OpenAI-compatible body
  - Streaming: iterate `.aiter_lines()`, parse `data: {...}` SSE lines, skip `data: [DONE]`, yield partial `GrokResponse`
  - Non-streaming fallback: parse single response JSON
  - Retry logic: `asyncio.sleep` exponential backoff (0.5s, 1s, 2s) for 429/500/502/503
- [ ] Create `scripts/smoke_test.py` — sends "Say hello in one sentence" to Grok and prints the streaming response to terminal
- [ ] Write unit tests using `respx` to mock the xAI API responses

### 1.4 — Core CLI Scaffold
- [ ] Create `grokcode/cli/main.py`:
  - `app = typer.Typer(name="grokcode", help="Agentic coding CLI powered by xAI Grok")`
  - `app.add_typer(workspace_app, name="workspace")`; same for `session_app`, `search_app`, `config_app`
  - Main entry: `@app.command() def run(task: Annotated[str, typer.Argument(...)], resume: bool = False, multi_agent: bool = False, auto_confirm: bool = False, debug: bool = False, dry_run: bool = False, session_id: str | None = None)`
- [ ] Create `grokcode/utils/ui.py` with `rich`-based helpers:
  - `def print_step(icon: str, text: str)` — coloured step line (e.g. `● Reading: path/to/file`)
  - `def print_success(text: str)` — green `✓ Done — ...`
  - `def print_error(text: str)` — red `rich.panel.Panel` with error message
  - `def confirm(prompt: str, auto: bool = False) -> bool` — `rich.prompt.Confirm.ask`; return `True` immediately if `auto=True`
  - `def print_diff(old: str, new: str, path: str)` — side-by-side or unified diff with `rich.syntax.Syntax`
  - `class AgentLiveDisplay` — context manager wrapping `rich.live.Live`; exposes `update_step(icon, text)` method
  - `class MultiAgentLiveDisplay` — `rich.live.Live` rendering a `rich.table.Table`; one row per sub-agent with spinner, ID, current action, status

---

## Phase 2: Agent Tools & Core Loop

### 2.1 — File System Tools
- [ ] Create `grokcode/tools/fs.py`:
  - `async def read_file(path: str) -> str` — read with `aiofiles.open`; raise `ToolError` if file > 100KB
  - `async def read_directory(path: str, recursive: bool = False) -> str` — return tree-formatted string; use `pathlib.Path.rglob("*")` for recursive, `iterdir()` otherwise
  - `async def write_file(path: str, content: str, auto_confirm: bool = False) -> str` — create parent dirs; if file exists, call `confirm()` unless `auto_confirm`
  - `async def edit_file(path: str, old_str: str, new_str: str) -> str` — read file content; count occurrences of `old_str`; raise `ToolError` if count != 1; replace and write; return edit summary
  - `async def delete_file(path: str, auto_confirm: bool = False) -> str` — always requires confirmation
- [ ] Define `FS_TOOL_SCHEMAS: list[dict]` — OpenAI-compatible tool schemas (JSON Schema) for each function
- [ ] Write unit tests using `pytest`'s `tmp_path` fixture

### 2.2 — Bash Execution Tool
- [ ] Create `grokcode/tools/bash.py`:
  - `class BashResult(BaseModel)`: `stdout: str`, `stderr: str`, `exit_code: int`
  - `class BashTool` with `_cwd: Path` instance state (tracks working directory across calls)
  - `async def execute(self, command: str, timeout: int = 30, auto_confirm: bool = False) -> BashResult`
  - Use `asyncio.create_subprocess_shell(..., stdout=PIPE, stderr=PIPE, cwd=self._cwd)`
  - Stream stdout lines to terminal via `rich.console.Console().print` as they arrive
  - `asyncio.wait_for(proc.communicate(), timeout=timeout)` — raise `ToolError` on timeout
  - Handle `cd <dir>` commands specially: update `self._cwd` instead of shelling out
  - Blocklist check before execution: reject `rm -rf /`, `sudo rm`, fork bombs; raise `ToolError` with message
  - Confirmation gate: commands whose first word is NOT in `SAFE_PREFIXES` (`pytest`, `python`, `pip`, `cat`, `ls`, `git`, `echo`, `find`, `grep`) must call `confirm()` unless `auto_confirm`
- [ ] Write unit tests mocking `asyncio.create_subprocess_shell`

### 2.3 — Git Tools
- [ ] Create `grokcode/tools/git.py` delegating to `BashTool`:
  - `async def git_status() -> str`
  - `async def git_diff(path: str | None = None) -> str`
  - `async def git_add(paths: list[str]) -> str`
  - `async def git_commit(message: str, auto_confirm: bool = False) -> str` — always requires confirmation
  - `async def git_log(n: int = 10) -> str`
  - `async def git_create_branch(name: str) -> str`
- [ ] Define `GIT_TOOL_SCHEMAS: list[dict]`
- [ ] Write unit tests

### 2.4 — Agent Core Loop
- [ ] Create `grokcode/agent/tool_registry.py`:
  - `class ToolRegistry`:
    - `register(name: str, fn: Callable, schema: dict)` — store in internal dict
    - `get_schemas() -> list[dict]` — return all OpenAI-format tool schemas
    - `async def execute(name: str, args: dict) -> ToolResult` — dispatch to registered fn; catch all exceptions; return error string as `ToolResult` content so agent can recover
- [ ] Create `grokcode/agent/system_prompt.py`:
  - `def build_system_prompt(config: AppConfig) -> str`
  - Base instructions block: agent identity, capabilities, safety rules
  - Append current datetime, `os.getcwd()`, active git branch (via `git_status`)
  - If `./GROKCODE.md` exists: read and append as `<project_instructions>` block
  - If workspace rules present: append as `<team_rules>` block (one rule per line)
- [ ] Create `grokcode/agent/agent.py`:
  - `class AgentEvent` — Pydantic discriminated union with subtypes: `ThinkingEvent`, `ToolCallEvent`, `ToolResultEvent`, `DoneEvent`, `ErrorEvent`
  - `class Agent`:
    - `__init__(self, config: AppConfig, tool_registry: ToolRegistry, grok_client: GrokClient)`
    - `async def run(self, task: str, history: list[Message] | None = None) -> AsyncGenerator[AgentEvent, None]`
  - Agent loop (max 25 iterations):
    1. Assemble `messages`: system prompt message + history + `{"role": "user", "content": task}`
    2. Call `grok_client.chat(messages, tools=registry.get_schemas())`; yield `ThinkingEvent` while streaming
    3. If response has `tool_calls`: for each call, yield `ToolCallEvent`; call `registry.execute(name, args)`; yield `ToolResultEvent`; append assistant + tool result messages to history
    4. If text response with no tool calls: yield `DoneEvent(text, usage)`; break
    5. On exception: yield `ErrorEvent`; break
- [ ] Wire to CLI: `run()` command creates `Agent`, iterates `agent.run(task)`, renders events via `AgentLiveDisplay`, saves session on completion
- [ ] End-to-end manual test: `grokcode "Create a Python function that returns the nth Fibonacci number, save it to fib.py"`

### 2.5 — Session Persistence
- [ ] Create `grokcode/session/session.py`:
  - `class Session(BaseModel)`: `id: str`, `task: str`, `started_at: datetime`, `history: list[Message]`, `files_modified: list[str]`, `status: Literal["active","done","interrupted"]`, `token_usage: TokenUsage | None`
  - `async def save_session(session: Session, sessions_dir: Path = DEFAULT_SESSIONS_DIR)`
  - `async def load_session(session_id: str) -> Session`
  - `async def list_sessions() -> list[Session]`
  - `async def get_last_session() -> Session | None`
  - Default sessions dir: `Path.home() / ".grokcode" / "sessions"`
- [ ] In CLI `run()`: create session at start; update `files_modified` after each `ToolResultEvent`; save on `DoneEvent` or `KeyboardInterrupt`
- [ ] `--resume` flag: call `get_last_session()`, pass `session.history` to `agent.run`
- [ ] `--session-id <id>` option: call `load_session(id)`, same as above
- [ ] Implement `grokcode session list` command — `rich` table: ID (truncated), task, status, started_at, token usage
- [ ] Write unit tests

---

## Phase 3: Team Workspace (Key Differentiator)

### 3.1 — xAI Collections API Client
> Check https://docs.x.ai for current Collections API endpoint paths and request formats

- [ ] Create `grokcode/workspace/collections_client.py`:
  - `class Collection(BaseModel)`: `id: str`, `name: str`, `created_at: datetime`
  - `class Document(BaseModel)`: `id: str`, `collection_id: str`, `metadata: dict`, `created_at: datetime`
  - `class SearchResult(BaseModel)`: `doc_id: str`, `content: str`, `score: float`, `metadata: dict`
  - `class CollectionsClient`:
    - `async def create_collection(name: str) -> Collection`
    - `async def upload_document(collection_id: str, content: str, metadata: dict) -> Document`
    - `async def delete_document(collection_id: str, doc_id: str) -> None`
    - `async def list_documents(collection_id: str) -> list[Document]`
    - `async def query_collection(collection_id: str, query: str, top_k: int = 5) -> list[SearchResult]`
- [ ] Write unit tests with `respx` mocks

### 3.2 — Workspace Commands
- [ ] Create `grokcode/workspace/workspace.py` with async business logic functions
- [ ] Create `grokcode/cli/workspace.py` — `workspace_app = typer.Typer()` with:
  - `@workspace_app.command("init")` — `def init(name: str, team_id: str = "default")`
    - Call `collections_client.create_collection(name)`
    - Write `grokcode.workspace.json` to `Path.cwd()` using `pydantic` model `.model_dump_json()`
    - Print `rich.panel.Panel` with success message + "Don't forget to `git add grokcode.workspace.json`"
  - `@workspace_app.command("index")` — `def index(paths: list[Path], tag: str = "")`
    - Collect all matching files recursively (`.py`, `.md`, `.json`, `.yaml`, `.toml`, `.txt`, `.rst`)
    - Show `rich.progress.Progress` bar during upload
    - Skip files > 100KB with a warning row in the progress display
    - Persist doc IDs to `.grokcode/workspace-index.json`
  - `@workspace_app.command("list")` — query Collection + display `rich` table
  - `@workspace_app.command("remove")` — `def remove(doc_id: str)` with confirmation
  - `@workspace_app.command("status")` — display `rich.panel.Panel` with workspace metadata
- [ ] Write unit tests for workspace business logic

### 3.3 — Collection-Grounded Agent
- [ ] In `Agent.run()`, before the first Grok call:
  - If `config.workspace_config` has a `collection_id`: call `collections_client.query_collection(collection_id, task, top_k=5)`
  - Format results as: `<workspace_context>\n[Source: {metadata.path}]\n{content}\n...\n</workspace_context>`
  - Inject this block into the system prompt (after team rules, before end of prompt)
- [ ] Add `search_workspace` as an agent tool:
  - `async def search_workspace(query: str) -> str` — calls `query_collection`, formats and returns results string
  - Register in `ToolRegistry` with schema
- [ ] Update `AgentLiveDisplay.update_step()` caller in the tool result handler to show `● Searching workspace knowledge...` when `search_workspace` is called
- [ ] Integration test: index `CODING_STANDARDS.md` with "always use type hints" rule → run coding task → assert generated code has type hints

### 3.4 — Session Handoff
- [ ] Create `grokcode/session/handoff.py`:
  - `class HandoffBundle(BaseModel)`: `name: str`, `session: Session`, `files_snapshot: dict[str, str]`
  - `async def export_session(session_id: str | None, name: str) -> HandoffBundle`:
    - Load session (last if `session_id` is None)
    - For each path in `session.files_modified`: read current file content async
    - Build `HandoffBundle`, write to `.grokcode/handoffs/<n>.json`
  - `async def import_session(name: str) -> Session`:
    - Read `.grokcode/handoffs/<n>.json`, parse `HandoffBundle`
    - Print `rich` summary panel: original task, files modified, session status
    - Return embedded `Session` (caller saves it as active via `save_session`)
- [ ] Implement `grokcode session export [--name <n>]` command
- [ ] Implement `grokcode session import <n>` command
- [ ] Write unit tests

### 3.5 — Workspace Rules Injection
- [ ] In `build_system_prompt()`, after GROKCODE.md block:
  - If `config.workspace_config` and `config.workspace_config.rules`: format as `<team_rules>\n- rule1\n- rule2\n</team_rules>`
- [ ] Read `config.workspace_config.mcp_servers` — store on `AppConfig` for use in Phase 3.6
- [ ] Unit test: call `build_system_prompt()` with a config that has 3 rules; assert all 3 appear in the output string

### 3.6 — Remote MCP Integration (Stretch)
- [ ] Create `grokcode/tools/mcp_client.py`:
  - `async def discover_tools(server_url: str) -> list[dict]` — GET the MCP tools discovery endpoint; return list of tool schemas
  - `async def call_mcp_tool(server_url: str, tool_name: str, args: dict) -> str` — POST tool call; return string result
- [ ] In `Agent.__init__()`: for each `McpServer` in config, call `discover_tools` and register each tool in `ToolRegistry` with a `partial(call_mcp_tool, server_url)` dispatcher
- [ ] Test: `grokcode "List my open Jira tickets"` (with Atlassian MCP server configured)

---

## Phase 4: Search, Multi-Agent & Polish

### 4.1 — Web & X Search Tools
- [ ] Create `grokcode/search/search.py`:
  - `class SearchResult(BaseModel)`: `title: str`, `url: str`, `snippet: str`, `source: str`
  - `async def web_search(query: str) -> list[SearchResult]` — call xAI web search tool via chat completions API
  - `async def x_search(query: str) -> list[SearchResult]` — call xAI X search tool via chat completions API
  - Both return formatted string summaries for use as tool results in the agent
- [ ] Register `web_search` and `x_search` in `ToolRegistry`
- [ ] Implement `grokcode search <query>` — call `web_search`, display as `rich` table (title, snippet, URL)
- [ ] Implement `grokcode xsearch <query>` — call `x_search`, display as `rich` table with source column
- [ ] Write unit tests with `respx` mocks

### 4.2 — Multi-Agent Task Execution
- [ ] Create `grokcode/agent/multi_agent.py`:
  - `class SubtaskPlan(BaseModel)`: `id: str`, `description: str`, `files: list[str]`, `agent_instructions: str`
  - `class MultiAgentResult(BaseModel)`: `subtasks_completed: int`, `files_modified: list[str]`, `test_output: str`, `summary: str`
  - `async def run_multi_agent(task: str, config: AppConfig, max_agents: int = 5) -> MultiAgentResult`:
    - Step 1: Run orchestrator `Agent` with system prompt instructing JSON output of `list[SubtaskPlan]`
    - Step 2: Parse JSON (strip markdown fences if present) into `list[SubtaskPlan]`
    - Step 3: Create semaphore `asyncio.Semaphore(max_agents)`; run sub-agents concurrently with `asyncio.gather`
    - Step 4: Collect all `files_modified` from sub-agent sessions; run merge agent for conflict resolution
    - Step 5: Run `pytest` (or `python -m pytest`) and capture output; include in result
- [ ] Update `MultiAgentLiveDisplay` to render live table updates as sub-agents emit events
- [ ] Add `--multi-agent` / `-m` flag and `--max-agents <n>` option to CLI `run` command
- [ ] Test with: `grokcode --multi-agent "Write pytest unit tests for every .py file in src/"`

### 4.3 — Audit Logging
- [ ] Create `grokcode/utils/audit.py`:
  - `class AuditEntry(BaseModel)`: `timestamp: datetime`, `session_id: str`, `tool: str`, `args_summary: str`, `result_summary: str`
  - `async def log_action(entry: AuditEntry)` — append `entry.model_dump_json() + "\n"` to `~/.grokcode/audit.log` using `aiofiles`
- [ ] Call `log_action` from `ToolRegistry.execute()` after every tool dispatch
- [ ] `grokcode config show` prints audit log path at the bottom of output
- [ ] Unit test for log appending

### 4.4 — Error Handling & UX Polish
- [ ] Add `app.exception_handler` or wrap `asyncio.run(main())` in try/except in `cli/main.py`:
  - Display `rich.panel.Panel` with friendly message for common errors (API key missing, file not found, network error)
  - Write full traceback to `~/.grokcode/error.log` using `traceback.format_exc()`
  - Print: `Details written to ~/.grokcode/error.log — use --debug to print here`
- [ ] `--debug` flag: set `logging.basicConfig(level=logging.DEBUG)`; `httpx` logs full request/response via `httpx` event hooks
- [ ] `--dry-run` flag: in `Agent.run()`, check flag before calling `tool_registry.execute()`; print what would be called instead
- [ ] `--auto-confirm` flag: pass through to all tool calls; bypass all `confirm()` calls
- [ ] Token usage display: after `DoneEvent`, print `rich.panel.Panel`: `Tokens used: {input} in / {output} out`
- [ ] Graceful `Ctrl+C`: catch `KeyboardInterrupt` in CLI `run()`; set `session.status = "interrupted"`; `asyncio.run(save_session(session))`; print "Session saved — resume with: grokcode --resume"

### 4.5 — Demo Scenario Setup Script
- [ ] Create `demo/setup.sh`:
  - Creates `demo/sample-app/` with a small FastAPI project (3–5 routes, a service layer, no tests yet)
  - Adds `demo/sample-app/docs/ARCHITECTURE.md` — describes FastAPI + Redis stack, auth design
  - Adds `demo/sample-app/CODING_STANDARDS.md` — Python 3.11+, type hints everywhere, Pydantic v2, pytest
  - Adds `demo/sample-app/openapi.yaml` — sample API spec with auth endpoints
- [ ] Create `demo/DEMO_SCRIPT.md` with numbered steps, exact commands, and expected `rich` output for the gravity9 xAI pitch
- [ ] Run the full demo end-to-end and confirm it works without errors

---

## Phase 5: Testing & Distribution

### 5.1 — Integration Tests
- [ ] `tests/integration/test_workspace.py`: init workspace → index file → run agent → assert collection query was made (mock xAI with `respx`)
- [ ] `tests/integration/test_handoff.py`: export session → import session → agent run has prior history in messages
- [ ] `tests/integration/test_multi_agent.py`: multi-agent on 3-file project → `MultiAgentResult.files_modified` contains all 3 files

### 5.2 — Build & Distribution
- [ ] Confirm `pip install -e ".[dev]"` works cleanly in a fresh venv
- [ ] Test `pipx install .` in a fresh environment and confirm `grokcode --help` runs
- [ ] Build: `python -m build` produces a valid `.whl` and `.tar.gz` in `dist/`
- [ ] Create `README.md` with:
  - Installation: `pipx install grokcode`
  - Quick start: `grokcode config set xai_api_key <key>` → `grokcode "Your first task"`
  - Team workspace setup guide
  - Full command reference table
  - ASCII architecture diagram

### 5.3 — CI/CD (Optional for PoC)
- [ ] `.github/workflows/ci.yml`: `ruff check .` → `mypy grokcode` → `pytest --cov=grokcode` on push to main
- [ ] `.github/workflows/release.yml`: `python -m build` + `twine upload dist/*` on version tag push

---

## Implementation Notes for Claude Code / Devin

### Environment Variables
```bash
XAI_API_KEY=xai-...   # xAI API key (or stored via keyring)
```

### xAI API Reference (see https://docs.x.ai)
- Chat completions: `POST https://api.x.ai/v1/chat/completions`
  - OpenAI-compatible: `model`, `messages`, `tools`, `stream`
  - Tool calling: `tools` array with `{"type": "function", "function": {"name", "description", "parameters"}}`
  - Tool call response: `choices[0].message.tool_calls` array with `id`, `function.name`, `function.arguments` (JSON string)
- Collections (RAG): check docs.x.ai for current endpoint paths
- Web Search + X Search: available as built-in tool types in the chat completions API

### Key Implementation Decisions

1. **Async throughout.** Use `asyncio` + `httpx.AsyncClient` everywhere. CLI entry point: `def main(): asyncio.run(_main())`. All test functions are `async def`. Use `pytest-asyncio` with `asyncio_mode = "auto"`.

2. **SSE streaming.** xAI uses OpenAI-compatible SSE. In `grok_client.py`, use `async with client.stream("POST", url, json=body) as resp: async for line in resp.aiter_lines(): ...`. Parse lines starting with `data: ` (strip prefix, parse JSON, skip `[DONE]`).

3. **Tool call format.** Tool schemas go in the `tools` list as `{"type": "function", "function": {...}}`. When Grok returns tool calls, `arguments` is a JSON *string* — always do `json.loads(tool_call.function.arguments)` before passing to the tool function.

4. **`edit_file` safety.** Count `content.count(old_str)` before replacing. If `!= 1`, raise `ToolError(f"old_str found {n} times — please provide a more specific string")`. The agent will retry with a better `old_str`.

5. **Collection query injection.** Inject workspace results as a block *inside the system message* (not as a separate message), appended after team rules. Keep it under 2000 tokens — truncate if needed.

6. **Message history format.** Store `list[dict]` compatible with the xAI API (`{"role": ..., "content": ...}`). Use `Message.model_dump(mode="json")` when sending. Tool result messages need `role: "tool"` and `tool_call_id`.

7. **`rich.live.Live` for multi-agent.** Use `Live(renderable=table, refresh_per_second=4)` as a context manager. Each sub-agent updates its own table row via a shared `table` reference. Use `Spinner` text in cells for active agents.

8. **`typer` subcommand pattern.** Each subcommand group file defines its own `typer.Typer()` instance (e.g., `workspace_app = typer.Typer()`). In `cli/main.py`: `app.add_typer(workspace_app, name="workspace")`. Callbacks are decorated with `@workspace_app.command("init")` etc.

9. **`keyring` on headless Linux.** If `keyring.get_password` raises `NoKeyringError`, fall back to env var and warn the user to set `XAI_API_KEY`. Suggest `pip install keyrings.alt` for Linux servers.

10. **JSON output from orchestrator.** When prompting the orchestrator for `SubtaskPlan[]`, use a system message like: "Respond ONLY with a JSON array. No markdown, no explanation." Then strip any ` ```json ` fences before `json.loads()`.

### Suggested Implementation Order
1. Config + Grok client (run smoke test to verify API connectivity)
2. File tools + bash tool (test manually with simple commands)
3. Agent loop + tool registry (wire up everything, run first real task)
4. Session persistence (`--resume` working)
5. **Collections client + workspace commands** ← highest priority for demo
6. Collection-grounded agent (workspace context injected into every task)
7. Session handoff (export/import)
8. Search tools (web + X)
9. Multi-agent
10. Error handling polish, `--dry-run`, token summary, audit log
11. Demo script + README