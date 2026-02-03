# Architecture

## Overview

nanoClaw is a small asyncio service that routes Telegram messages to an agent
loop, executes tools, stores memory in SQLite, and exposes a local dashboard.

## Runtime Flow

1. A channel (Telegram or console) receives a message.
2. Gateway routes the message to the agent.
3. Agent builds context, selects tools, calls the LLM, and executes tools.
4. Memory store saves history and long-term facts.
5. Audit log records every action.
6. Scheduler can send proactive messages via the gateway.

## Modules

- `nanoclaw/core`: agent loop, context builder, config, LLM client, logging.
- `nanoclaw/tools`: core tools (shell, files, web, memory, spawn) and registry.
- `nanoclaw/skills`: built-in skills loaded from disk.
- `nanoclaw/security`: sandbox, file guard, prompt guard, audit, budget.
- `nanoclaw/memory`: SQLite store for history and memories.
- `nanoclaw/channels`: gateway, Telegram bot, console.
- `nanoclaw/cron`: scheduler for recurring jobs.
- `nanoclaw/dashboard`: local aiohttp server and single-file UI.

## Data Stores

- SQLite at `~/.nanoclaw/data/nanoclaw.db` for history, memories, cron, audit.

## Dependencies

- aiohttp
- python-telegram-bot
- click
- pydantic
- sqlite3 (stdlib)
- html2text
- croniter

## Security Boundaries

- FileGuard restricts file access to `~/.nanoclaw/workspace`.
- ShellSandbox blocks dangerous commands and confirms destructive ones.
- PromptGuard sanitizes tool output and detects injection patterns.
- Dashboard binds to localhost only and Telegram IDs are allow-listed.
