# Project Context

## Purpose

nanoClaw is an ultra-lightweight, secure-by-default AI assistant designed for 24/7 operation. Inspired by OpenClaw, it achieves the same core functionality in ~3,000 lines of code (vs OpenClaw's 430,000 lines) with a 2-minute setup time. It provides a secure AI agent that runs locally, integrates with Telegram and other channels, and executes tools with multiple security layers.

## Tech Stack

### Core
- **Python 3.11+** - Required runtime
- **asyncio** - Async/await for all I/O operations
- **SQLite3** (stdlib) - Persistent storage for history, memory, cron, audit logs
- **Pydantic 2.0+** - Data validation and config management

### Web & Networking
- **aiohttp 3.9+** - Async HTTP client (LLM API, web tools, dashboard)
- **python-telegram-bot 20.0+** - Telegram bot integration
- **websockets 12.0+** - WebSocket support
- **requests 2.31+** - Sync HTTP for specific use cases
- **html2text 2024.2+** - HTML to text conversion

### Agent & LLM
- **deepagents 0.1.0+** - Agent framework (recently integrated)
- **langgraph 0.2.0+** - Agent orchestration
- **langchain-openai 0.1.0+** - OpenAI integration
- **langchain-anthropic 0.1.0+** - Anthropic/Claude integration
- **tavily-python 0.5.0+** - Web search
- **langchain-modal 0.0.2+** - Modal integration
- **langchain-community 0.4.1+** - Community integrations

### Utilities
- **click 8.0+** - CLI framework
- **pycryptodome 3.19+** - Cryptographic operations
- **croniter 1.3+** - Cron expression parsing

### Optional Dependencies
- **chromadb 0.4+** - Semantic search (memory feature)

## Project Conventions

### Code Style

**Language**: Everything in English (code, comments, commits, docs, error messages)

**Formatting**:
- Max line length: 100 characters
- Type hints on all function signatures
- Docstrings on every public class/function (one-liners acceptable)
- `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants
- No em dashes (—), en dashes (–), or unicode arrows (→, ←, ↔) - use ASCII: `--`, `->`, `<-`, `=>`
- No smart quotes - use straight quotes only (" and ')
- No emoji in source code or logs (only in user-facing Telegram messages/CLI where specified)

**Imports**:
- Order: stdlib → third-party → local (separated by blank lines)
- No wildcard imports (`from x import *`)
- Lazy imports for optional deps (chromadb, croniter) inside functions, not at module level

**Structure**:
- Single responsibility per file
- Files exceeding 300 lines should be split
- `__init__.py` files minimal: version info and re-exports only

### Architecture Patterns

**Module Structure**:
- `nanoclaw/core` - Agent loop, context builder, config, LLM client, logging
- `nanoclaw/tools` - Core tools (shell, files, web, memory, spawn) and registry
- `nanoclaw/skills` - Built-in skills loaded from disk
- `nanoclaw/security` - Sandbox, file guard, prompt guard, audit, budget
- `nanoclaw/memory` - SQLite store for history and memories
- `nanoclaw/channels` - Gateway, Telegram bot, console, eteams
- `nanoclaw/cron` - Scheduler for recurring jobs
- `nanoclaw/dashboard` - Local aiohttp server and UI
- `nanoclaw/deepagents` - DeepAgents framework integration

**Runtime Flow**:
1. Channel receives message (Telegram/console/eteams)
2. Gateway routes to agent
3. Agent builds context, selects tools, calls LLM, executes tools
4. Memory store saves history and facts
5. Audit log records all actions
6. Scheduler can send proactive messages via gateway

**Execution Patterns**:
- **ReAct (default)**: User message → LLM (with tools) → tool_calls → parallel execute → LLM → response
- **Automatic Escalation**: After 4 iterations without final answer, inject planning nudge (zero extra cost)

**Security Layers** (defense in depth):
1. **FileGuard** - Restricts file access to workspace only
2. **ShellSandbox** - Blocks dangerous commands, confirms destructive ones
3. **PromptGuard** - Detects and sanitizes prompt injection attempts
4. **SessionBudget** - Rate limiting and cost controls
5. **AuditLog** - Logs all agent actions
6. **SecurityDoctor** - Validates installation security

### Testing Strategy

**Framework**: pytest + pytest-asyncio

**Guidelines**:
- Write tests for security modules first (sandbox, file guard, prompt guard)
- Tests should run without API keys or network (mock external calls)
- Test files mirror source: `tests/test_<module>.py` for `nanoclaw/<module>.py`
- Each security layer needs: 3 positive cases (allowed), 3 negative cases (blocked)
- Test with adversarial inputs: path traversal, command injection, prompt injection

### Git Workflow

**Branching**: Main branch is `main`. Use feature branches as needed.

**Commit Format**: `type: short description`
- Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`
- Examples: `feat: add shell sandbox`, `fix: handle timeout`, `docs: update architecture`
- Keep commits atomic - one logical change per commit
- Never mention AI tools (Claude, Copilot, etc.) in commit messages
- Write commits as if a human developer wrote the code

**What NOT to Commit**:
- Generated files
- `__pycache__`, `.pyc`
- `config.json` (contains API keys)
- Workspace contents
- Virtual environments

## Domain Context

**Target User**: Developers and technical users who want a secure, lightweight AI assistant that can execute shell commands and manage files.

**Core Use Cases**:
- Web search and information retrieval
- File operations in a sandboxed workspace
- Shell command execution (with safety guards)
- Persistent memory across conversations
- Background task spawning
- Scheduled/recurring tasks
- Integration with multiple chat platforms (Telegram, eteams)

**Key Differentiator**: Token efficiency. Average message costs under $0.01 vs OpenClaw's $0.05-0.10 through dynamic tool injection, smart history windowing, and aggressive output compression.

## Important Constraints

### Code Size
**Target**: ~3,000 lines total
- Every line must earn its place
- No abstractions without 2+ concrete uses
- Prefer stdlib over external packages
- No wrapper classes that just delegate

### Performance
**Response Time Targets**:
- Simple question (no tools): <2s
- Single tool call: <4s
- Multi-tool parallel (3 tools): <5s
- Research (5+ iterations): <15s

**Token Efficiency**:
- System prompt: <400 tokens
- Tool schemas: 5-7 tools (~800 tokens), not all tools
- History: 4-15 messages, truncated
- Tool outputs: compressed (1500-4000 chars per tool)

**Runtime Efficiency**:
- All I/O is async (no blocking calls in event loop)
- Shared aiohttp session (one per application lifecycle)
- Parallel tool execution with `asyncio.gather`
- SQLite operations wrapped in `asyncio.to_thread`
- Session cache for expensive operations

### Security
**Critical Rules**:
- All file paths go through `FileGuard.validate_path()` - no exceptions
- All shell commands go through `ShellSandbox` - no direct subprocess/os.system
- All tool outputs go through `PromptGuard.sanitize_tool_output()`
- Never log API keys, tokens, or passwords
- Never add secrets to default config, examples, tests, or README

**Error Handling**:
- Every `async with`, `await`, and external call must have try/except
- Tools return string results, never raise unhandled exceptions
- User-facing errors must be clear and actionable

### Dependencies
**Rules**:
- Minimize dependencies - every new package needs justification
- Pin versions with minimum bounds (`>=`), not exact (`==`)
- No heavy frameworks: no langchain core, llamaindex, fastapi, flask, django, react
- Check stdlib first before adding dependencies

**Forbidden**:
- Adding features not in spec without explicit approval
- Refactoring working code without functional reason
- Creating abstract base classes without 2+ implementations
- Adding retry logic everywhere (tools should fail fast)
- Over-engineering - keep it simple

## External Dependencies

### Required Services
**LLM Providers** (at least one required):
- **OpenRouter** (recommended) - Access to all major models
- **DeepSeek** - deepseek-chat, deepseek-reasoner
- **Anthropic** - Claude Sonnet/Opus/Haiku
- **OpenAI** - GPT family
- **Local** - Ollama, LM Studio

**Chat Platforms** (at least one required):
- **Telegram** - Bot token from @BotFather
- **Eteams** - Custom enterprise IM integration
- **Console** - CLI chat for testing

### Optional Services
- **Brave Search API** - Web search capability
- **Tailscale** - Secure networking for dashboard access

### Data Storage
- **SQLite** - Local database at `~/.nanoclaw/data/nanoclaw.db`
  - Stores: history, memories, cron jobs, audit logs
  - WAL mode enabled for concurrent reads during writes
  - FTS5 full-text search for memories

### Configuration
- Config file: `~/.nanoclaw/config.json`
- Workspace: `~/.nanoclaw/workspace/`
- Skills directory: `~/.nanoclaw/skills/`
- Dashboard: localhost:18790 (local only)

### External APIs Used
- LLM provider APIs (chosen by user)
- Brave Search API (optional)
- GitHub API (for github_repo_info skill)
- Weather API (for get_weather skill)
- News sources (for get_news skill)
