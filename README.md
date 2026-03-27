# GrokCode

Agentic coding CLI powered by xAI Grok — with built-in **Team Workspace** and an interactive REPL.

```
$ grokcode

╭─ GrokCode v0.1.0 ────────────────────────────────────────────────────────────╮
│                                Tips for getting started                       │
│   Welcome back loghman!        ────────────────────────────────────           │
│                                Run /init to create a GROKCODE.md file        │
│   ██╗  ██╗ █████╗  ██╗         with instructions for Grok                    │
│   ╚██╗██╔╝ ██╔══██╗ ██║                                                       │
│    ╚██╔╝   ███████║ ██║        Type any task to run the agent                │
│    ██╔██╗  ██╔══██║ ██║        /help for all commands                        │
│   ██╔╝ ██╗ ██║  ██║ ██║                                                       │
│   ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚═╝        Recent activity                               │
│                                ────────────────────────────────────           │
│   grok-3-mini · acme           Add rate limiting to /api/auth endpoints       │
│   ~/Desktop/my-project           2026-03-27                                   │
╰───────────────────────────────────────────────────────────────────────────────╯

>
```

---

## Why GrokCode?

| Capability | Claude Code | GrokCode |
|---|---|---|
| Agentic coding in CLI | ✅ | ✅ |
| File read/write/edit | ✅ | ✅ |
| Bash + Git operations | ✅ | ✅ |
| **Interactive REPL interface** | ❌ | ✅ |
| **Team Workspace (shared context)** | ❌ | ✅ |
| **Session handoff between teammates** | ❌ | ✅ |
| **Multi-agent parallel tasks** | ❌ | ✅ |
| **Real-time X + Web search** | ❌ | ✅ |
| Native model | Claude | Grok |

---

## Installation

```bash
# Recommended
pipx install grokcode

# Or with pip
pip install grokcode
```

**Requirements:** Python 3.11+, an [xAI API key](https://console.x.ai)

---

## Quick Start

```bash
# 1. Set your API key (stored in system keychain)
grokcode config set xai_api_key xai-YOUR-KEY-HERE

# 2. Open the interactive REPL
grokcode

# 3. Type any task at the prompt
> Add a /health endpoint to the FastAPI app

# 4. Or run a one-shot task directly
grokcode run "Create a Python function that returns the nth Fibonacci number"
```

---

## Interactive REPL

Running `grokcode` with no arguments opens the interactive REPL — a persistent environment
where you type tasks or slash commands until you exit.

```
> Add rate limiting to the /api/auth endpoints
> /sessions
> /config model
> /xsearch fastapi-limiter async issues 2025
> /exit
```

### REPL Slash Commands

| Command | Description |
|---|---|
| **Agent** | |
| `<task>` | Run an agentic coding task |
| `/multi-agent <task>` | Run task with parallel sub-agents |
| `/dry-run <task>` | Show what the agent would do without executing |
| `/resume` | Resume the last session |
| `/resume <id>` | Resume a specific session by ID |
| **Search** | |
| `/search <query>` | Search the web via xAI |
| `/xsearch <query>` | Search X (Twitter) for real-time signals |
| **Session** | |
| `/sessions` | List all saved sessions |
| `/session export <name>` | Export current session for teammate handoff |
| `/session import <name>` | Import a teammate's exported session |
| **Workspace** | |
| `/workspace` | Show workspace status |
| `/workspace init <name>` | Create a new team workspace |
| `/workspace index <paths>` | Index files into the team knowledge base |
| `/workspace list` | List indexed documents |
| **Config** | |
| `/config` | Show current configuration |
| `/config model` | Interactively select the Grok model |
| `/config set <key> <value>` | Set a config value (e.g. theme, max_tokens) |
| **General** | |
| `/init` | Create a GROKCODE.md with instructions for Grok |
| `/help` | Show all commands |
| `/exit`, `/quit` | Exit GrokCode |

---

## Model Selection

Run `/config model` in the REPL to interactively switch between Grok models:

```
> /config model

  Current model: grok-3-mini

  ┌────┬──────────────────────┬────────────────────────────────────────┐
  │ 1  │ grok-4               │ Most capable — best for complex tasks  │
  │ 2  │ grok-3               │ Powerful and precise                   │
  │ 3  │ grok-3-fast          │ Faster grok-3 with lower latency       │
  │ ▶4 │ grok-3-mini          │ Efficient — great for everyday tasks   │
  │ 5  │ grok-3-mini-fast     │ Fastest response, lightweight tasks    │
  │ 6  │ grok-2-1212          │ Previous generation, stable            │
  │ 7  │ grok-2-vision-1212   │ Previous generation with vision        │
  └────┴──────────────────────┴────────────────────────────────────────┘

  Enter a number to switch model, or press Enter to keep current:
  > 1
  ✓ Model updated: grok-4
```

The selected model is saved to `~/.grokcode/config.json` and takes effect immediately.

---

## Team Workspace Setup

The Team Workspace is GrokCode's key differentiator — a shared, RAG-grounded knowledge base
built on xAI Collections. Every engineer's agent automatically queries it on every task.

```bash
# 1. Initialize workspace (creates an xAI Vector Store)
grokcode workspace init --name "acme-platform" --team-id acme

# 2. Commit the workspace config so teammates can use it
git add grokcode.workspace.json && git commit -m "Add GrokCode workspace"

# 3. Index your docs, ADRs, coding standards into the shared knowledge base
grokcode workspace index ./docs ./ADRs ./CODING_STANDARDS.md ./openapi.yaml
```

Or use REPL slash commands:

```
> /workspace init acme-platform
> /workspace index ./docs ./CODING_STANDARDS.md
> /workspace list
```

**`grokcode.workspace.json`** (commit this to your repo):
```json
{
  "workspace": "acme-platform",
  "collection_id": "vs_abc123",
  "team_id": "acme",
  "rules": [
    "Always use Python type hints on all function signatures",
    "Use Pydantic v2 for data validation",
    "Never expose PII in logs",
    "Test files must use pytest with async support"
  ],
  "mcp_servers": [
    { "name": "jira", "url": "https://mcp.atlassian.com/v1/mcp" }
  ]
}
```

---

## Session Handoff

Hand off your AI session to a teammate with full context — no catch-up meeting needed.

```bash
# Developer A: export current session
grokcode session export --name "auth-jwt-refactor"

# Developer B: import and continue
grokcode session import "auth-jwt-refactor"
grokcode run --resume "The Redis connection is failing in CI, fix it"
```

Or in the REPL:

```
> /session export auth-jwt-refactor
> /session import auth-jwt-refactor
> /resume
```

---

## Multi-Agent Tasks

For complex tasks, GrokCode spawns parallel sub-agents:

```bash
grokcode run --multi-agent "Write unit tests for every service in src/services/"
grokcode run --multi-agent --max-agents 3 "Add type hints to all Python files"
```

Or in the REPL:

```
> /multi-agent Write pytest unit tests for every service in src/services/
```

The orchestrator decomposes the task → sub-agents run concurrently with file-level locking
to prevent conflicts → results merged → tests run.

---

## Search

```bash
# Web search (standalone)
grokcode search web "FastAPI rate limiting best practices"

# X (Twitter) search — real-time ecosystem signals
grokcode search x "fastapi-limiter deprecated 2025"
```

Or in the REPL:

```
> /search FastAPI rate limiting best practices
> /xsearch fastapi-limiter deprecated 2025
```

Search is also available as agent tools — the agent uses them autonomously when needed.

---

## CLI Command Reference

```
grokcode                                Open interactive REPL

grokcode run <task>                     Run a task (one-shot)
grokcode run --resume                   Resume last session
grokcode run --session-id <id>          Resume a specific session
grokcode run --multi-agent <task>       Spawn multi-agent for complex task
grokcode run --dry-run <task>           Show what would be done without executing
grokcode run --auto-confirm <task>      Skip all confirmation prompts
grokcode run --debug <task>             Enable debug logging

grokcode workspace init                 Initialize team workspace
grokcode workspace index <path>...      Index files into team Collection
grokcode workspace list                 List indexed documents
grokcode workspace remove --doc-id <id> Remove a document
grokcode workspace status               Show workspace health

grokcode session export --name <name>   Export session for handoff
grokcode session import <name>          Import a teammate's session
grokcode session list                   List all sessions

grokcode search web <query>             Web search (standalone)
grokcode search x <query>               X search (standalone)

grokcode config set <key> <value>       Set config (API key, model, etc.)
grokcode config show                    Show current config
```

---

## Configuration

**User config** (`~/.grokcode/config.json`):
```json
{
  "model": "grok-3-mini",
  "max_tokens": 8192,
  "auto_confirm": false,
  "theme": "dark"
}
```

**Supported config keys:**

| Key | Default | Description |
|---|---|---|
| `xai_api_key` | — | xAI API key (stored in system keychain) |
| `model` | `grok-3-mini` | Grok model to use (use `/config model` to select interactively) |
| `max_tokens` | `8192` | Max tokens per response |
| `auto_confirm` | `false` | Skip confirmation prompts |
| `theme` | `dark` | Terminal theme |

**Available models:**

| Model | Description |
|---|---|
| `grok-4` | Most capable — best for complex coding tasks |
| `grok-3` | Powerful and precise |
| `grok-3-fast` | Faster grok-3 with lower latency |
| `grok-3-mini` | Efficient — great for everyday tasks *(default)* |
| `grok-3-mini-fast` | Fastest response, lightweight tasks |
| `grok-2-1212` | Previous generation, stable |
| `grok-2-vision-1212` | Previous generation with vision support |

---

## Project Instructions (GROKCODE.md)

Create a `GROKCODE.md` in your project root — analogous to `CLAUDE.md`. GrokCode reads it at
every session start. Run `/init` in the REPL to create one from a template:

```markdown
# My Project — GrokCode Instructions

## Stack
- FastAPI + Redis + PostgreSQL
- Python 3.11+, Pydantic v2

## Conventions
- Services in src/services/ — no HTTP concerns
- Routes in src/routers/ — no business logic
- Tests use pytest-asyncio with httpx.AsyncClient
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     GrokCode CLI                         │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  REPL / TUI  │  │ Session Mgr  │  │ Workspace Mgr │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
│         └────────────────►│◄──────────────────┘          │
│                    ┌──────▼───────┐                       │
│                    │  Agent Core  │                        │
│                    │  (Grok API)  │                        │
│                    └──────┬───────┘                       │
│         ┌─────────────────┼──────────────────┐           │
│         ▼                 ▼                  ▼           │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Tool Runner │  │  xAI Search  │  │  MCP Client  │    │
│  │ (fs, bash,  │  │  (Web + X)   │  │ (Jira, Slack)│    │
│  │  git)       │  └──────────────┘  └──────────────┘    │
│  └─────────────┘                                         │
└─────────────────────────────────────────────────────────┘
                          │
                    xAI Platform
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    ┌──────────┐  ┌──────────────┐  ┌──────────────┐
    │  Grok    │  │  Collections │  │  Multi-Agent │
    │   API    │  │  (RAG/Team   │  │     Beta     │
    └──────────┘  │  Workspace)  │  └──────────────┘
                  └──────────────┘
```

---

## Security

- API keys stored in system keychain (`keyring`) — never in plain text files
- All destructive operations require `y/n` confirmation (bypass with `--auto-confirm`)
- All agent actions logged to `~/.grokcode/audit.log`
- `--dry-run` mode shows planned actions without executing anything

---

## Development

```bash
# Clone and install in editable mode
git clone https://github.com/gravity9/grokcode
cd grokcode
pip install -e ".[dev]"

# Run tests
pytest

# Lint + format
ruff check . && ruff format .

# Type check
mypy grokcode

# Smoke test (requires XAI_API_KEY)
python scripts/smoke_test.py
```

---

## License

MIT © gravity9
