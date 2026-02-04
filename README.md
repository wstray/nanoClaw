# nanoClaw

Ultra-lightweight secure personal AI assistant that lives in Telegram.

```
OpenClaw:  430,000 lines, complex setup, security concerns
nanoClaw:   ~3,000 lines, secure by default, 2-min setup
```

## Features

- **Secure by default** - file system sandbox, shell command filtering, prompt injection defense
- **Model-agnostic** - Claude, GPT-5, DeepSeek, Gemini via OpenRouter or direct API
- **Ultra-lightweight** - ~3000 lines total, minimal dependencies
- **2-minute setup** - interactive wizard guides configuration
- **No open ports** - Telegram polling, dashboard on localhost only
- **Persistent memory** - remembers facts about you across conversations
- **Background tasks** - spawn long-running research jobs
- **Scheduled jobs** - cron-like recurring tasks
- **Web dashboard** - monitor activity, manage settings

## Quick Start

### Installation

```bash
git clone https://github.com/ysz/nanoClaw
cd nanoclaw
pip install -e .
```

### Setup

Run the interactive wizard:

```bash
nanoclaw init
```

The wizard will:
1. Configure your LLM provider (OpenRouter recommended)
2. Set up Telegram bot connection
3. Optionally enable web search (Brave API)
4. Run security checks

### Usage

Start the agent:

```bash
nanoclaw serve
```

Then message your bot on Telegram!

### CLI Chat (Testing)

```bash
# Interactive chat
nanoclaw chat

# One-shot message
nanoclaw chat -m "What's the weather in Tokyo?"
```

### Other Commands

```bash
# Check status
nanoclaw status

# Run security audit
nanoclaw doctor

# Manage scheduled tasks
nanoclaw cron list
nanoclaw cron add --name "Morning news" --message "Summarize tech news" --every 86400
nanoclaw cron remove 1
```

## Architecture

```
You (Telegram) --> [nanoClaw Server] --> LLM API
                        |
    +-------------------+-------------------+
    |           |           |           |
  Agent      Memory      Tools       Security
  Loop       (SQLite)    (sandboxed)  (6 layers)
    |
  Dashboard (localhost:18790)
```

### Security Layers

1. **FileGuard** - restricts file access to workspace only
2. **ShellSandbox** - blocks dangerous commands, confirms destructive ones
3. **PromptGuard** - detects and sanitizes prompt injection attempts
4. **SessionBudget** - rate limiting and cost controls
5. **AuditLog** - logs all agent actions
6. **SecurityDoctor** - validates installation security

## Configuration

Config is stored at `~/.nanoclaw/config.json`:

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-..."
    }
  },
  "agents": {
    "defaults": {
      "model": "anthropic/claude-sonnet-4-5"
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  },
  "tools": {
    "webSearch": {
      "apiKey": "BRAVE_API_KEY"
    }
  },
  "dashboard": {
    "enabled": true,
    "port": 18790
  }
}
```

## Built-in Tools

- `web_search` - search the internet (Brave API)
- `web_fetch` - fetch and read web pages
- `shell_exec` - execute shell commands (sandboxed)
- `file_read/write/list` - file operations in workspace
- `memory_save/search` - persistent memory
- `spawn_task` - background tasks

## Built-in Skills

- `get_weather` - weather lookup
- `github_repo_info` - GitHub repository info
- `get_news` - news search
- `summarize_url` - URL summarization
- `get_time` - time in different cities

## Custom Skills

Add Python files to `~/.nanoclaw/skills/`:

```python
from nanoclaw.tools.registry import tool

@tool(
    name="my_skill",
    description="Does something useful",
    parameters={"arg": {"type": "string", "description": "Argument"}}
)
async def my_skill(arg: str) -> str:
    return f"Result: {arg}"
```

Skills are auto-loaded on startup.

## Docker

```bash
docker run -d \
  --name nanoclaw \
  --restart unless-stopped \
  -v ~/.nanoclaw/config.json:/app/config/config.json:ro \
  -v ~/.nanoclaw/workspace:/app/workspace \
  -v ~/.nanoclaw/data:/app/data \
  -p 127.0.0.1:18790:18790 \
  nanoclaw/nanoclaw:latest
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type check
mypy nanoclaw/

# Lint
ruff check nanoclaw/
```

## Supported Providers

| Provider | Models | Get API Key |
|----------|--------|-------------|
| OpenRouter | All major models | [openrouter.ai/keys](https://openrouter.ai/keys) |
| DeepSeek | deepseek-chat, deepseek-reasoner | [platform.deepseek.com](https://platform.deepseek.com) |
| Anthropic | Claude Sonnet/Opus/Haiku | [console.anthropic.com](https://console.anthropic.com) |
| OpenAI | GPT-5 family | [platform.openai.com](https://platform.openai.com) |
| Local | Ollama, LM Studio | - |

## Requirements

- Python 3.11+
- Telegram Bot Token (from @BotFather)
- LLM API key (any provider above)
- Optional: Brave Search API key

## License

MIT
