# GrokCode CLI — Product Specification

**Version:** 0.1 (PoC)
**Owner:** gravity9
**Platform:** xAI (Grok)
**Status:** Pre-implementation

---

## 1. Vision & Positioning

GrokCode is an agentic coding CLI powered by xAI's Grok platform, purpose-built for software development teams. It delivers Claude Code–style agentic coding in the terminal with a key native differentiator: **Team Workspace** — a built-in shared context layer that lets multiple engineers collaborate within the same AI-assisted coding environment without ever leaving the CLI.

Where Claude Code is a single-user agent, GrokCode is team-native from day one. Shared knowledge, shared memory, and multi-agent task coordination are first-class citizens, not add-ons.

---

## 2. Target Users

| Persona | Description |
|---|---|
| Solo Developer | Uses GrokCode for agentic code generation, refactoring, and debugging — same as Claude Code |
| Team Lead | Manages the team workspace: uploads codebase conventions, architecture docs, ADRs |
| Engineering Team | Multiple engineers sharing a live project context, handing off AI sessions, running parallel agents |
| gravity9 Consultants | Onboard quickly to client codebases using the shared team Collection |

---

## 3. Key Differentiators vs Claude Code

| Capability | Claude Code | GrokCode |
|---|---|---|
| Agentic coding in CLI | ✅ | ✅ |
| File read/write/edit | ✅ | ✅ |
| Bash execution | ✅ | ✅ |
| Git operations | ✅ | ✅ |
| Multi-file context | ✅ | ✅ |
| **Team Workspace (shared context)** | ❌ | ✅ |
| **Shared codebase Collections (RAG)** | ❌ | ✅ |
| **Session handoff between teammates** | ❌ | ✅ |
| **Multi-agent parallel task execution** | ❌ | ✅ (beta) |
| **Real-time X + Web search** | ❌ | ✅ |
| **Remote MCP (Jira, Slack, etc.)** | Limited | ✅ |
| Native model | Claude | Grok 4 |

---

## 4. Core Features

### 4.1 Agentic Coding Loop (Claude Code Parity)

The core interaction model mirrors Claude Code: the user types a task in natural language, and GrokCode autonomously plans and executes steps using tools.

**Tools available to the agent:**
- `read_file(path)` — Read a single file
- `read_directory(path, recursive?)` — List or traverse directory structure
- `write_file(path, content)` — Create or overwrite a file
- `edit_file(path, old_str, new_str)` — Precise string-replacement edits (safe, targeted)
- `execute_bash(command, timeout?)` — Run shell commands (tests, builds, installs)
- `git_status()` / `git_diff()` / `git_commit(msg)` — Git lifecycle ops
- `web_search(query)` — Grok web search for docs, libraries, StackOverflow
- `x_search(query)` — X (Twitter) search for real-time ecosystem signals

**Interaction flow:**
```
$ grokcode "Refactor the auth module to use JWT and add unit tests"
  
  ● Planning...
  ● Reading: src/auth/auth.py, src/auth/session.py
  ● Editing: src/auth/auth.py
  ● Creating: tests/auth/test_auth.py
  ● Running: pytest tests/auth/
  ✓ Done — 3 files changed, all tests passing
```

**Session persistence:** Each session stores conversation history locally (`.grokcode/sessions/`), allowing `--resume` to continue interrupted work.

**GROKCODE.md:** Project-level instruction file (analogous to `CLAUDE.md`). GrokCode always reads this at session start for project context, conventions, and constraints.

---

### 4.2 Team Workspace (Core Differentiator)

The Team Workspace is a shared, persistent context layer built on **xAI Collections** (native RAG). It gives every engineer on the team access to the same indexed knowledge about the project — architecture docs, ADRs, API specs, coding standards — without manual context injection.

#### 4.2.1 Workspace Initialization

```bash
grokcode workspace init --name "acme-platform" --team-id acme
```

Creates a named xAI Collection that is the team's shared knowledge base. The Collection ID is stored in a shared config (e.g., committed `grokcode.workspace.json`).

#### 4.2.2 Knowledge Ingestion

Team leads (or CI pipelines) push documents into the shared Collection:

```bash
# Index files/directories into the team Collection
grokcode workspace index ./docs ./ADRs ./openapi.yaml

# Index with metadata tags
grokcode workspace index ./src/auth --tag "auth-module"

# Remove a document
grokcode workspace remove --doc-id <id>

# List indexed documents
grokcode workspace list
```

The agent automatically queries the Collection (with citations) on every task to ground its responses in team knowledge.

#### 4.2.3 Session Handoff

A developer can export their current session context and share it with a teammate:

```bash
# Export session snapshot to the team workspace
grokcode session export --name "auth-jwt-refactor"

# Teammate picks it up
grokcode session import "auth-jwt-refactor"

# Teammate resumes with full context
grokcode "Continue the JWT refactor — tests are failing on the refresh token flow"
```

Exported sessions store: conversation history, files touched, last known state, and open TODOs. These are stored in the shared workspace (xAI Collection or a lightweight shared store).

#### 4.2.4 Shared Rules & Conventions

`grokcode.workspace.json` (committed to the repo) defines team-wide rules:

```json
{
  "workspace": "acme-platform",
  "collection_id": "xai-collection-abc123",
  "team_id": "acme",
  "rules": [
    "Always use Python type hints on all function signatures",
    "Use Pydantic v2 for data validation and serialization",
    "Never expose PII in logs",
    "Test files must use pytest with async support"
  ],
  "mcp_servers": [
    { "name": "jira", "url": "https://mcp.atlassian.com/v1/mcp" },
    { "name": "slack", "url": "https://mcp.slack.com/mcp" }
  ]
}
```

These rules are automatically injected into every system prompt, so every engineer's agent behaves consistently.

---

### 4.3 Multi-Agent Task Coordination (xAI Multi-Agent Beta)

For complex tasks, GrokCode can spawn sub-agents to work on isolated subtasks in parallel:

```bash
grokcode --multi-agent "Add authentication to all API endpoints"
```

Internally:
1. **Orchestrator agent** (Grok 4) decomposes the task into subtasks
2. **Sub-agents** (Grok 4 instances) execute each subtask concurrently
3. Orchestrator merges results, resolves conflicts, runs tests
4. User sees a unified summary

This is particularly valuable for:
- Large refactors across many files
- Generating tests for an entire module
- Implementing a feature across multiple services

---

### 4.4 Real-Time Search Integration

Unique to xAI's platform, GrokCode has access to both web search and X (Twitter) search natively:

- **Web Search:** Used for library docs, error messages, Stack Overflow, GitHub issues
- **X Search:** Used for real-time ecosystem signals — "is this library deprecated?", "what's the community saying about this breaking change?", framework announcements

These are available as agent tools and also as explicit user commands:

```bash
grokcode search "Prisma v6 breaking changes"
grokcode xsearch "Vite 6 migration issues"
```

---

### 4.5 Remote MCP Tool Integration

GrokCode reads `mcp_servers` from `grokcode.workspace.json` and makes those tools available to the agent. No additional setup per developer.

**Supported integrations (via MCP):**
- Jira — create/update tickets, link commits to issues
- Slack — post summaries, notify channels
- GitHub/GitLab — PR creation, issue management
- Salesforce, MongoDB (for gravity9 client contexts)

**Example:**
```bash
grokcode "Implement the feature described in PROJ-1234 and open a PR when done"
```
→ Agent reads Jira ticket → implements feature → runs tests → creates GitHub PR → posts Slack notification

---

## 5. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     GrokCode CLI                         │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  REPL / TUI  │  │ Session Mgr  │  │ Workspace Mgr │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
│         └────────────────►│◄──────────────────┘          │
│                    ┌──────▼───────┐                       │
│                    │ Agent Core   │                        │
│                    │ (Grok 4)     │                        │
│                    └──────┬───────┘                       │
│         ┌─────────────────┼─────────────────┐            │
│         ▼                 ▼                 ▼            │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Tool Runner │  │  xAI Search  │  │  MCP Client  │    │
│  │ (fs, bash,  │  │  (Web + X)   │  │  (Jira,Slack)│    │
│  │  git)       │  └──────────────┘  └──────────────┘    │
│  └─────────────┘                                         │
└─────────────────────────────────────────────────────────┘
                          │
                    xAI Platform
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    ┌──────────┐  ┌──────────────┐  ┌──────────────┐
    │  Grok 4  │  │  Collections │  │  Multi-Agent │
    │   API    │  │  (RAG/Team   │  │     Beta     │
    └──────────┘  │   Workspace) │  └──────────────┘
                  └──────────────┘
```

---

## 6. CLI Interface Design

### 6.1 Commands

```
grokcode <task>                         # Run a task (main agent loop)
grokcode --resume                       # Resume last session
grokcode --multi-agent <task>           # Spawn multi-agent for complex task

grokcode workspace init                 # Initialize team workspace
grokcode workspace index <path>         # Index files into team Collection
grokcode workspace list                 # List indexed documents
grokcode workspace remove --doc-id <id> # Remove a document
grokcode workspace status               # Show workspace health

grokcode session export [--name <name>] # Export session for handoff
grokcode session import <name>          # Import a teammate's session
grokcode session list                   # List available sessions

grokcode search <query>                 # Web search (standalone)
grokcode xsearch <query>                # X search (standalone)

grokcode config set <key> <value>       # Set config (API key, model, etc.)
grokcode config show                    # Show current config
```

### 6.2 Configuration

`~/.grokcode/config.json` (user-level):
```json
{
  "xai_api_key": "xai-...",
  "model": "grok-4",
  "max_tokens": 8192,
  "auto_confirm": false,
  "theme": "dark"
}
```

`./grokcode.workspace.json` (project-level, committed):
```json
{
  "workspace": "project-name",
  "collection_id": "...",
  "team_id": "...",
  "rules": [],
  "mcp_servers": []
}
```

---

## 7. Security & Safety

- **Confirmation gates:** All destructive operations (file overwrites, `rm`, git push) require explicit `y/n` confirmation unless `--auto-confirm` is set
- **Sandbox mode:** `--sandbox` flag runs bash commands in a Docker container
- **API key storage:** Keys stored in system keychain (via `keyring`), never in plain text files
- **Workspace access:** Collection access governed by xAI API key scoping
- **Audit log:** All agent actions logged to `.grokcode/audit.log`

---

## 8. Non-Functional Requirements

| Requirement | Target |
|---|---|
| First response latency | < 3s (streaming) |
| File operation throughput | Support repos up to 500k LOC |
| Session export size | < 5MB per session snapshot |
| Workspace Collection size | Up to 1000 documents |
| Multi-agent tasks | Up to 5 parallel sub-agents |
| Platform | macOS, Linux (Python 3.11+) |
| Distribution | `pipx install grokcode` / `pip install grokcode` |

---

## 9. PoC Scope (1 Week)

For the gravity9 xAI partnership demo, the PoC covers:

| Feature | In Scope | Notes |
|---|---|---|
| Core agent loop (read/write/bash/git) | ✅ | Full implementation |
| Grok 4 integration | ✅ | Via xAI API |
| GROKCODE.md support | ✅ | |
| Team Workspace (Collection init + index) | ✅ | Key differentiator demo |
| Collection-grounded responses | ✅ | With citations |
| Session export/import | ✅ | Simplified (JSON file) |
| Web + X Search | ✅ | Via xAI native search |
| Multi-agent tasks | ✅ (basic) | Orchestrator + 2 sub-agents |
| Remote MCP (Jira/Slack) | ⚠️ Stretch | If time allows |
| Sandbox mode | ❌ | Post-PoC |
| Full auth/access control | ❌ | Post-PoC |

---

## 10. Demo Scenario (for gravity9 xAI Pitch)

**Setup:** A sample Python/FastAPI repo representing a client codebase.

**Demo flow:**
1. `grokcode workspace init` — create team Collection, index architecture docs + coding standards
2. Developer A: `grokcode "Add rate limiting to the /api/auth endpoints"` — agent reads Collection, knows the team uses FastAPI + Redis, implements correctly, cites the architecture doc
3. Developer A: `grokcode session export --name "rate-limit-feature"`
4. Developer B (another terminal): `grokcode session import "rate-limit-feature"` → `grokcode "The Redis connection is failing in the CI environment, fix it"` — picks up with full context
5. `grokcode --multi-agent "Write unit tests for every service in /src/services"` — spawns parallel sub-agents, tests generated in ~60s
6. `grokcode "What are people saying about fastapi-limiter on X right now?"` — X Search live demo

---

## 11. Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.11+ |
| CLI framework | `typer` (type-safe, built on Click) |
| Terminal UI | `rich` (spinners, tables, syntax highlighting, live progress) |
| HTTP client | `httpx` (async, streaming SSE support) |
| Data models | `pydantic` v2 (typed config, messages, sessions) |
| Tool execution | `asyncio.subprocess` + `pathlib` |
| Session storage | Local JSON files in `.grokcode/` |
| Workspace storage | xAI Collections API |
| Keychain | `keyring` (cross-platform secure key storage) |
| Testing | `pytest` + `pytest-asyncio` + `respx` (mock httpx) |
| Distribution | `pipx install grokcode` / `pip install grokcode` |
| Packaging | `pyproject.toml` (PEP 621) with `hatchling` or `flit` |