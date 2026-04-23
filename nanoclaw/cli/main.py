"""CLI commands for nanoClaw."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Callable

import click


# --- Interactive selector (arrow keys navigation) ---

def _read_key() -> str:
    """Read a single keypress from terminal. Returns key name."""
    try:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":  # Escape sequence
                ch2 = sys.stdin.read(1)
                if ch2 == "[":
                    ch3 = sys.stdin.read(1)
                    if ch3 == "A":
                        return "up"
                    elif ch3 == "B":
                        return "down"
                return "escape"
            elif ch in ("\r", "\n"):
                return "enter"
            elif ch == "\x03":  # Ctrl+C
                raise KeyboardInterrupt
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except ImportError:
        # Windows fallback
        try:
            import msvcrt

            ch = msvcrt.getch()  # type: ignore[attr-defined]
            if ch in (b"\x00", b"\xe0"):  # Special key prefix
                ch2 = msvcrt.getch()  # type: ignore[attr-defined]
                if ch2 == b"H":
                    return "up"
                elif ch2 == b"P":
                    return "down"
            elif ch == b"\r":
                return "enter"
            return ch.decode("utf-8", errors="ignore")
        except ImportError:
            return input() or "enter"


def _clear_lines(n: int) -> None:
    """Move cursor up n lines and clear them."""
    for _ in range(n):
        sys.stdout.write("\x1b[A")  # Move up
        sys.stdout.write("\x1b[2K")  # Clear line
    sys.stdout.flush()


def select(
    options: list[tuple[str, str]],
    title: str = "",
    default: int = 0,
) -> int:
    """
    Interactive selector with arrow key navigation.

    Args:
        options: List of (value, label) tuples
        title: Optional title to display
        default: Default selected index

    Returns:
        Selected index
    """
    # Check if we have a real terminal
    if not sys.stdin.isatty():
        # Fallback to numbered input
        if title:
            click.echo(title)
        for i, (_, label) in enumerate(options):
            marker = ">" if i == default else " "
            click.echo(f"  {marker} {i + 1}. {label}")
        choice = click.prompt("Choice", type=int, default=default + 1)
        return max(0, min(choice - 1, len(options) - 1))

    selected = default

    def render() -> None:
        if title:
            click.echo(title)
        for i, (_, label) in enumerate(options):
            if i == selected:
                # Highlighted: cyan background or inverse
                click.echo(f"  \x1b[36m> {label}\x1b[0m")
            else:
                click.echo(f"    {label}")

    render()
    lines_to_clear = len(options) + (1 if title else 0)

    try:
        while True:
            key = _read_key()
            if key == "up":
                selected = (selected - 1) % len(options)
            elif key == "down":
                selected = (selected + 1) % len(options)
            elif key == "enter":
                # Clear and show final selection
                _clear_lines(lines_to_clear)
                _, label = options[selected]
                if title:
                    click.echo(title)
                click.echo(f"  \x1b[32m> {label}\x1b[0m")
                return selected
            elif key == "escape":
                return default

            # Re-render
            _clear_lines(lines_to_clear)
            render()
    except KeyboardInterrupt:
        click.echo("\nAborted.")
        sys.exit(1)


def confirm_interactive(prompt: str, default: bool = True) -> bool:
    """Interactive yes/no with arrow keys."""
    options = [("yes", "Yes"), ("no", "No")]
    default_idx = 0 if default else 1
    result = select(options, title=prompt, default=default_idx)
    return result == 0


@click.group()
@click.version_option(package_name="nanoclaw-ai")
def cli() -> None:
    """nanoClaw - Secure personal AI assistant"""
    pass


@cli.command()
def init() -> None:
    """Initialize nanoClaw with interactive wizard."""
    asyncio.run(setup_wizard())


async def setup_wizard() -> None:
    """Interactive setup wizard."""
    click.echo("\nWelcome to nanoClaw setup!\n")

    config: dict = {}

    # Step 1: LLM Provider
    providers = [
        ("openrouter", "OpenRouter (recommended - one key, all models)"),
        ("anthropic", "Anthropic API"),
        ("openai", "OpenAI API"),
        ("deepseek", "DeepSeek API"),
        ("local", "Local model (Ollama, LM Studio, etc.)"),
    ]
    choice = select(providers, title="Step 1/4: LLM Provider", default=0)

    if choice == 0:  # OpenRouter
        click.echo()
        api_key = click.prompt("  OpenRouter API key (openrouter.ai/keys)")
        config["providers"] = {"openrouter": {"apiKey": api_key}}

        click.echo()
        models = [
            ("anthropic/claude-sonnet-4-5", "claude-sonnet-4.5 (recommended)"),
            ("anthropic/claude-opus-4-5", "claude-opus-4.5 (smartest)"),
            ("openai/gpt-5", "gpt-5"),
            ("openai/gpt-5-mini", "gpt-5-mini (fast)"),
            ("google/gemini-3-pro", "gemini-3-pro"),
            ("google/gemini-3-flash", "gemini-3-flash (fast)"),
            ("deepseek/deepseek-chat", "deepseek-v3.2 (budget)"),
            ("deepseek/deepseek-reasoner", "deepseek-reasoner (thinking)"),
        ]
        model_idx = select(models, title="  Choose default model:", default=0)
        config["agents"] = {"defaults": {"model": models[model_idx][0]}}

    elif choice == 1:  # Anthropic
        click.echo()
        api_key = click.prompt("  Anthropic API key")
        click.echo()
        models = [
            ("claude-sonnet-4-5", "claude-sonnet-4.5 (recommended)"),
            ("claude-opus-4-5", "claude-opus-4.5 (smartest)"),
            ("claude-haiku-4-5", "claude-haiku-4.5 (fast, cheap)"),
        ]
        model_idx = select(models, title="  Choose model:", default=0)
        config["providers"] = {
            "anthropic": {
                "apiKey": api_key,
                "defaultModel": models[model_idx][0],
            }
        }

    elif choice == 2:  # OpenAI
        click.echo()
        api_key = click.prompt("  OpenAI API key")
        click.echo()
        models = [
            ("gpt-5", "gpt-5 (recommended)"),
            ("gpt-5.2", "gpt-5.2 (latest)"),
            ("gpt-5.1", "gpt-5.1"),
            ("gpt-5-mini", "gpt-5-mini (fast, cheap)"),
            ("gpt-5-nano", "gpt-5-nano (fastest, cheapest)"),
        ]
        model_idx = select(models, title="  Choose model:", default=0)
        config["providers"] = {
            "openai": {"apiKey": api_key, "defaultModel": models[model_idx][0]}
        }

    elif choice == 3:  # DeepSeek
        click.echo()
        api_key = click.prompt("  DeepSeek API key (platform.deepseek.com)")
        click.echo()
        models = [
            ("deepseek-chat", "deepseek-chat (V3)"),
            ("deepseek-reasoner", "deepseek-reasoner (R1)"),
        ]
        model_idx = select(models, title="  Choose model:", default=0)
        config["providers"] = {
            "deepseek": {
                "apiKey": api_key,
                "defaultModel": models[model_idx][0],
            }
        }

    elif choice == 4:  # Local model
        click.echo()
        local_providers = [
            ("ollama", "Ollama (localhost:11434)"),
            ("lmstudio", "LM Studio (localhost:1234)"),
            ("custom", "Custom URL"),
        ]
        local_choice = select(local_providers, title="  Local provider:", default=0)
        click.echo()

        if local_choice == 0:  # Ollama
            base_url = "http://localhost:11434/v1"
            model = click.prompt("  Model name (e.g., llama3, mistral)", default="llama3")
        elif local_choice == 1:  # LM Studio
            base_url = "http://localhost:1234/v1"
            model = click.prompt("  Model name", default="local-model")
        else:  # Custom
            base_url = click.prompt("  Base URL")
            model = click.prompt("  Model name")

        api_key = click.prompt("  API key (leave empty if not required)", default="", show_default=False)
        config["providers"] = {
            "openai": {
                "apiKey": api_key or "not-needed",
                "defaultModel": model,
                "baseUrl": base_url,
            }
        }

    # Step 2: Telegram
    click.echo()
    use_telegram = confirm_interactive("Step 2/4: Connect Telegram?", default=True)
    if use_telegram:
        click.echo()
        token = click.prompt("  Bot token (from @BotFather)")
        user_id = click.prompt("  Your Telegram user ID (from @userinfobot)")
        config["channels"] = {
            "telegram": {"enabled": True, "token": token, "allowFrom": [user_id]}
        }
    else:
        config["channels"] = {"telegram": {"enabled": False}}

    # Step 3: Web Search
    click.echo()
    use_search = confirm_interactive("Step 3/5: Enable web search?", default=True)
    if use_search:
        click.echo()
        search_key = click.prompt(
            "  Brave Search API key (brave.com/search/api, leave empty to skip)",
            default="",
            show_default=False,
        )
        if search_key:
            config["tools"] = {"webSearch": {"apiKey": search_key}}

    # Step 4: Langfuse Tracing
    click.echo()
    use_langfuse = confirm_interactive("Step 4/5: Enable Langfuse observability/tracing?", default=False)
    if use_langfuse:
        click.echo()
        click.echo("  Get your API keys from: https://cloud.langfuse.com (or your self-hosted instance)")
        public_key = click.prompt("  Langfuse Public Key (pk-lf-...)", default="", show_default=False)
        secret_key = click.prompt("  Langfuse Secret Key (sk-lf-...)", default="", show_default=False)

        if public_key and secret_key:
            host = click.prompt(
                "  Langfuse Host",
                default="https://cloud.langfuse.com",
                show_default=True
            )
            config["langfuse"] = {
                "enabled": True,
                "publicKey": public_key,
                "secretKey": secret_key,
                "host": host,
            }
            click.echo("  Langfuse tracing enabled!")
        else:
            click.echo("  Skipping Langfuse (keys not provided)")

    # Step 5: Save
    click.echo("\nStep 5/5: Saving configuration...")

    config_dir = Path.home() / ".nanoclaw"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "workspace").mkdir(exist_ok=True)
    (config_dir / "data").mkdir(exist_ok=True)

    config_path = config_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2))

    # Set secure permissions
    try:
        config_path.chmod(0o600)
        (config_dir / "workspace").chmod(0o700)
    except Exception:
        pass  # May fail on Windows

    click.echo(f"  Config saved: {config_path}")
    click.echo(f"  Workspace: {config_dir / 'workspace'}")

    # Run security check
    click.echo("\n  Running security check...")
    from nanoclaw.security.doctor import SecurityDoctor

    doctor = SecurityDoctor()
    results = await doctor.check_all()
    for r in results:
        icon = "[OK]" if r.passed else "[!!]" if r.severity == "critical" else "[??]"
        click.echo(f"  {icon} {r.name}: {r.message}")

    click.echo(
        """
nanoClaw is ready!

  Start agent:    nanoclaw serve
  Chat from CLI:  nanoclaw chat "hello"
  View status:    nanoclaw status
  Security check: nanoclaw doctor
"""
    )


@cli.command()
@click.option("-m", "--message", help="One-shot message")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed logs (tool calls, thinking)")
def chat(message: str | None, verbose: bool) -> None:
    """Chat with nanoClaw agent."""
    if verbose:
        import os
        os.environ["NANOCLAW_VERBOSE"] = "1"
        from nanoclaw.core.logger import set_verbose
        set_verbose(True)
    if message:
        asyncio.run(one_shot_chat(message))
    else:
        asyncio.run(interactive_chat())


async def one_shot_chat(message: str) -> None:
    """Run a single message through the agent."""
    from nanoclaw.core.agent import get_agent
    from nanoclaw.core.llm import ConnectionPool
    from nanoclaw.tools.shell import set_confirm_callback

    async def cli_confirm(question: str) -> bool:
        click.echo(f"\n{question}")
        return click.confirm("Allow?", default=False)

    set_confirm_callback(cli_confirm)

    try:
        agent = get_agent()
        response = await agent.run(message, session_id="cli")
        click.echo(f"\n{response}")
    finally:
        # Flush telemetry data before exit
        agent = get_agent()
        await agent.flush()
        await ConnectionPool.close()


async def interactive_chat() -> None:
    """Interactive chat REPL."""
    from nanoclaw.core.agent import get_agent
    from nanoclaw.core.llm import ConnectionPool
    from nanoclaw.tools.shell import set_confirm_callback

    async def cli_confirm(question: str) -> bool:
        click.echo(f"\n{question}")
        return click.confirm("Allow?", default=False)

    set_confirm_callback(cli_confirm)

    click.echo("nanoClaw Interactive Chat")
    click.echo("Type 'exit' or 'quit' to leave\n")

    agent = get_agent()
    session_id = "cli_interactive"

    try:
        while True:
            try:
                user_input = click.prompt("You", prompt_suffix="> ")
            except (EOFError, KeyboardInterrupt):
                break

            if user_input.lower() in ("exit", "quit"):
                break

            response = await agent.run(user_input, session_id=session_id)
            click.echo(f"\nAssistant: {response}\n")
    finally:
        # Flush telemetry data before exit
        await agent.flush()
        await ConnectionPool.close()


@cli.command()
@click.option("-v", "--verbose", is_flag=True, help="Show detailed logs (tool calls, thinking)")
def serve(verbose: bool) -> None:
    """Start nanoClaw gateway (Telegram + Cron + Dashboard)."""
    if verbose:
        import os
        import logging
        os.environ["NANOCLAW_VERBOSE"] = "1"
        # Import and set verbose BEFORE any other nanoclaw imports
        from nanoclaw.core.logger import set_verbose
        set_verbose(True)
        # Verify logger state
        root = logging.getLogger("nanoclaw")
        click.echo(f"Verbose logging enabled (level={root.level}, handlers={len(root.handlers)})")
    asyncio.run(start_gateway())


async def start_gateway() -> None:
    """Start the gateway with all components."""
    from nanoclaw.channels.gateway import Gateway
    from nanoclaw.core.config import get_config

    config = get_config()
    gateway = Gateway(config)
    await gateway.start()


@cli.command()
def status() -> None:
    """Show nanoClaw status."""
    asyncio.run(show_status())


async def show_status() -> None:
    """Display current status."""
    from nanoclaw.core.config import get_config
    from nanoclaw.memory.store import get_memory_store
    from nanoclaw.security.audit import get_audit_log

    try:
        config = get_config()
    except FileNotFoundError:
        click.echo("nanoClaw not configured. Run 'nanoclaw init' first.")
        return

    click.echo("\nnanoClaw Status")
    click.echo("=" * 40)

    # Provider
    provider, _, model, _ = config.get_active_provider()
    click.echo(f"Provider: {provider}")
    click.echo(f"Model: {model}")

    # Channels
    click.echo(f"\nTelegram: {'enabled' if config.channels.telegram.enabled else 'disabled'}")
    click.echo(f"Dashboard: {'enabled' if config.dashboard.enabled else 'disabled'}")

    # Observability
    langfuse_status = 'enabled' if config.langfuse.enabled else 'disabled'
    if config.langfuse.enabled and config.langfuse.host:
        langfuse_status += f" ({config.langfuse.host})"
    click.echo(f"Langfuse: {langfuse_status}")

    # Stats
    try:
        memory = get_memory_store()
        stats = await memory.get_stats()
        click.echo(f"\nMessages: {stats['total_messages']}")
        click.echo(f"Sessions: {stats['sessions']}")
        click.echo(f"Memories: {stats['memories']}")
        click.echo(f"Cron jobs: {stats['cron_jobs']}")
    except Exception:
        pass

    # Today's audit stats
    try:
        audit = get_audit_log()
        today = await audit.get_stats_today()
        click.echo("\nToday's activity:")
        click.echo(f"  Messages: {today['messages']}")
        click.echo(f"  Tool calls: {today['tool_calls']}")
        click.echo(f"  Tokens: {today['total_tokens']}")
        if today['errors'] > 0:
            click.echo(f"  Errors: {today['errors']}")
        if today['blocked'] > 0:
            click.echo(f"  Blocked: {today['blocked']}")
    except Exception:
        pass


@cli.command()
def doctor() -> None:
    """Run security check."""
    asyncio.run(run_doctor())


async def run_doctor() -> None:
    """Run security doctor checks."""
    from nanoclaw.security.doctor import SecurityDoctor

    doctor = SecurityDoctor()
    results = await doctor.check_all()
    click.echo(doctor.format_report(results))


@cli.group()
def cron() -> None:
    """Manage scheduled tasks."""
    pass


@cron.command()
@click.option("--name", required=True, help="Job name")
@click.option("--message", required=True, help="Message to send to agent")
@click.option("--cron", "cron_expr", help="Cron expression (e.g., '0 9 * * *')")
@click.option("--every", type=int, help="Repeat every N seconds")
def add(name: str, message: str, cron_expr: str | None, every: int | None) -> None:
    """Add a scheduled task."""
    asyncio.run(add_cron_job(name, message, cron_expr, every))


async def add_cron_job(
    name: str, message: str, cron_expr: str | None, every: int | None
) -> None:
    """Add a cron job."""
    from nanoclaw.cron.scheduler import get_scheduler

    if not cron_expr and not every:
        click.echo("Error: Must specify --cron or --every")
        return

    scheduler = get_scheduler()
    job_id = await scheduler.add_job(
        name=name,
        message=message,
        cron_expr=cron_expr,
        interval_seconds=every,
    )
    click.echo(f"Created job #{job_id}: {name}")


@cron.command("list")
def list_jobs() -> None:
    """List all scheduled tasks."""
    asyncio.run(list_cron_jobs())


async def list_cron_jobs() -> None:
    """List cron jobs."""
    from nanoclaw.cron.scheduler import get_scheduler

    scheduler = get_scheduler()
    jobs = await scheduler.list_jobs()

    if not jobs:
        click.echo("No scheduled jobs.")
        return

    click.echo("\nScheduled Jobs:")
    click.echo("-" * 60)
    for job in jobs:
        status = "enabled" if job["enabled"] else "disabled"
        schedule = job["cron_expr"] or f"every {job['interval_seconds']}s"
        click.echo(f"#{job['id']} [{status}] {job['name']}")
        click.echo(f"   Schedule: {schedule}")
        click.echo(f"   Message: {job['message'][:50]}...")
        click.echo()


@cron.command()
@click.argument("job_id", type=int)
def remove(job_id: int) -> None:
    """Remove a scheduled task."""
    asyncio.run(remove_cron_job(job_id))


async def remove_cron_job(job_id: int) -> None:
    """Remove a cron job."""
    from nanoclaw.cron.scheduler import get_scheduler

    scheduler = get_scheduler()
    await scheduler.remove_job(job_id)
    click.echo(f"Removed job #{job_id}")


# --- Config management ---


@cli.command()
def config() -> None:
    """Interactive config editor."""
    config_path = Path.home() / ".nanoclaw" / "config.json"
    if not config_path.exists():
        click.echo("No config found. Run 'nanoclaw init' first.")
        return

    data = json.loads(config_path.read_text())

    def save() -> None:
        config_path.write_text(json.dumps(data, indent=2))

    while True:
        # Show current status
        click.echo("\n  Current configuration:")
        provider, model = _get_current_provider_info(data)
        click.echo(f"  Provider: {provider}")
        click.echo(f"  Model: {model}")
        tg_enabled = data.get("channels", {}).get("telegram", {}).get("enabled", False)
        click.echo(f"  Telegram: {'enabled' if tg_enabled else 'disabled'}")
        brave_key = data.get("tools", {}).get("webSearch", {}).get("apiKey", "")
        click.echo(f"  Web search: {'configured' if brave_key else 'not configured'}")
        langfuse_enabled = data.get("langfuse", {}).get("enabled", False)
        click.echo(f"  Langfuse: {'enabled' if langfuse_enabled else 'disabled'}")
        click.echo()

        options = [
            ("provider", "LLM Provider & Model"),
            ("telegram", "Telegram"),
            ("tools", "Tools (web search, etc.)"),
            ("langfuse", "Langfuse Observability"),
            ("show", "Show full config (JSON)"),
            ("exit", "Exit"),
        ]
        choice = select(options, title="  Settings:", default=0)

        if choice == 0:
            _edit_provider(data, save)
        elif choice == 1:
            _edit_telegram(data, save)
        elif choice == 2:
            _edit_tools(data, save)
        elif choice == 3:
            _edit_langfuse(data, save)
        elif choice == 4:
            masked = _mask_secrets(data)
            click.echo(json.dumps(masked, indent=2))
        elif choice == 5:
            break

    click.echo("Done.")


def _get_current_provider_info(data: dict) -> tuple[str, str]:
    """Get current provider and model from config."""
    providers = data.get("providers", {})
    if "deepseek" in providers:
        model = providers["deepseek"].get("defaultModel", "")
        return "DeepSeek", model
    elif "openrouter" in providers:
        model = data.get("agents", {}).get("defaults", {}).get("model", "")
        return "OpenRouter", model
    elif "anthropic" in providers:
        model = providers["anthropic"].get("defaultModel", "")
        return "Anthropic", model
    elif "openai" in providers:
        model = providers["openai"].get("defaultModel", "")
        base_url = providers["openai"].get("baseUrl", "")
        if base_url:
            return "Local/Custom", model
        return "OpenAI", model
    return "Not configured", ""


def _mask_secrets(obj: dict | list | str, key: str = "") -> dict | list | str:
    """Recursively mask sensitive values."""
    sensitive_keys = {"apiKey", "apikey", "token", "password", "secret", "sessionToken"}

    if isinstance(obj, dict):
        return {k: _mask_secrets(v, k) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_mask_secrets(item, key) for item in obj]
    elif isinstance(obj, str) and key in sensitive_keys and obj:
        return obj[:4] + "****" + obj[-4:] if len(obj) > 8 else "****"
    return obj


def _edit_provider(data: dict, save: Callable[[], None]) -> None:
    """Edit LLM provider settings."""
    while True:
        click.echo()
        provider, model = _get_current_provider_info(data)
        click.echo(f"  Current: {provider} / {model}")
        click.echo()

        options = [
            ("openrouter", "OpenRouter"),
            ("anthropic", "Anthropic API"),
            ("openai", "OpenAI API"),
            ("deepseek", "DeepSeek API"),
            ("local", "Local model"),
            ("model", "Change model only"),
            ("back", "Back"),
        ]
        choice = select(options, title="  Select provider:", default=0)

        if choice == 6:  # Back
            return

        if choice == 5:  # Change model only
            _change_model_only(data, save)
            continue

        # Clear old providers
        data["providers"] = {}

        if choice == 0:  # OpenRouter
            click.echo()
            click.echo("  (leave empty to cancel)")
            api_key = click.prompt("  OpenRouter API key", default="", show_default=False)
            if not api_key:
                click.echo("  Cancelled.")
                continue
            models = [
                ("anthropic/claude-sonnet-4-5", "claude-sonnet-4.5"),
                ("anthropic/claude-opus-4-5", "claude-opus-4.5"),
                ("openai/gpt-5", "gpt-5"),
                ("google/gemini-3-pro", "gemini-3-pro"),
                ("deepseek/deepseek-chat", "deepseek-v3.2"),
                ("back", "Back"),
            ]
            click.echo()
            model_idx = select(models, title="  Model:", default=0)
            if models[model_idx][0] == "back":
                click.echo("  Cancelled.")
                continue
            data["providers"]["openrouter"] = {"apiKey": api_key}
            data["agents"] = {"defaults": {"model": models[model_idx][0]}}

        elif choice == 1:  # Anthropic
            click.echo()
            click.echo("  (leave empty to cancel)")
            api_key = click.prompt("  Anthropic API key", default="", show_default=False)
            if not api_key:
                click.echo("  Cancelled.")
                continue
            models = [
                ("claude-sonnet-4-5", "claude-sonnet-4.5"),
                ("claude-opus-4-5", "claude-opus-4.5"),
                ("claude-haiku-4-5", "claude-haiku-4.5"),
                ("back", "Back"),
            ]
            click.echo()
            model_idx = select(models, title="  Model:", default=0)
            if models[model_idx][0] == "back":
                click.echo("  Cancelled.")
                continue
            data["providers"]["anthropic"] = {
                "apiKey": api_key,
                "defaultModel": models[model_idx][0],
            }

        elif choice == 2:  # OpenAI
            click.echo()
            click.echo("  (leave empty to cancel)")
            api_key = click.prompt("  OpenAI API key", default="", show_default=False)
            if not api_key:
                click.echo("  Cancelled.")
                continue
            models = [
                ("gpt-5", "gpt-5"),
                ("gpt-5.2", "gpt-5.2"),
                ("gpt-5-mini", "gpt-5-mini"),
                ("gpt-5-nano", "gpt-5-nano"),
                ("back", "Back"),
            ]
            click.echo()
            model_idx = select(models, title="  Model:", default=0)
            if models[model_idx][0] == "back":
                click.echo("  Cancelled.")
                continue
            data["providers"]["openai"] = {
                "apiKey": api_key,
                "defaultModel": models[model_idx][0],
            }

        elif choice == 3:  # DeepSeek
            click.echo()
            click.echo("  (leave empty to cancel)")
            api_key = click.prompt("  DeepSeek API key (platform.deepseek.com)", default="", show_default=False)
            if not api_key:
                click.echo("  Cancelled.")
                continue
            models = [
                ("deepseek-chat", "deepseek-chat (V3)"),
                ("deepseek-reasoner", "deepseek-reasoner (R1)"),
                ("back", "Back"),
            ]
            click.echo()
            model_idx = select(models, title="  Model:", default=0)
            if models[model_idx][0] == "back":
                click.echo("  Cancelled.")
                continue
            data["providers"]["deepseek"] = {
                "apiKey": api_key,
                "defaultModel": models[model_idx][0],
            }

        elif choice == 4:  # Local
            click.echo()
            click.echo("  (leave both empty to cancel)")
            base_url = click.prompt("  Base URL", default="http://localhost:11434/v1")
            model = click.prompt("  Model name", default="llama3")
            # Only cancel if user explicitly cleared defaults
            if not base_url and not model:
                click.echo("  Cancelled.")
                continue
            data["providers"]["openai"] = {
                "apiKey": "not-needed",
                "defaultModel": model or "llama3",
                "baseUrl": base_url or "http://localhost:11434/v1",
            }

        save()
        click.echo("  Saved.")
        return  # Exit to main menu after saving


def _change_model_only(data: dict, save: Callable[[], None]) -> None:
    """Change model without changing provider."""
    providers = data.get("providers", {})

    if "deepseek" in providers:
        models = [
            ("deepseek-chat", "deepseek-chat (V3)"),
            ("deepseek-reasoner", "deepseek-reasoner (R1)"),
            ("back", "Back"),
        ]
        click.echo()
        model_idx = select(models, title="  Model:", default=0)
        if models[model_idx][0] == "back":
            return
        data["providers"]["deepseek"]["defaultModel"] = models[model_idx][0]

    elif "openrouter" in providers:
        models = [
            ("anthropic/claude-sonnet-4-5", "claude-sonnet-4.5"),
            ("anthropic/claude-opus-4-5", "claude-opus-4.5"),
            ("openai/gpt-5", "gpt-5"),
            ("google/gemini-3-pro", "gemini-3-pro"),
            ("deepseek/deepseek-chat", "deepseek-v3.2"),
            ("back", "Back"),
        ]
        click.echo()
        model_idx = select(models, title="  Model:", default=0)
        if models[model_idx][0] == "back":
            return
        if "agents" not in data:
            data["agents"] = {}
        if "defaults" not in data["agents"]:
            data["agents"]["defaults"] = {}
        data["agents"]["defaults"]["model"] = models[model_idx][0]

    elif "anthropic" in providers:
        models = [
            ("claude-sonnet-4-5", "claude-sonnet-4.5"),
            ("claude-opus-4-5", "claude-opus-4.5"),
            ("claude-haiku-4-5", "claude-haiku-4.5"),
            ("back", "Back"),
        ]
        click.echo()
        model_idx = select(models, title="  Model:", default=0)
        if models[model_idx][0] == "back":
            return
        data["providers"]["anthropic"]["defaultModel"] = models[model_idx][0]

    elif "openai" in providers:
        base_url = providers["openai"].get("baseUrl")
        if base_url:
            # Local - manual input
            click.echo()
            click.echo("  (leave empty to cancel)")
            model = click.prompt("  Model name", default="", show_default=False)
            if not model:
                click.echo("  Cancelled.")
                return
            data["providers"]["openai"]["defaultModel"] = model
        else:
            models = [
                ("gpt-5", "gpt-5"),
                ("gpt-5.2", "gpt-5.2"),
                ("gpt-5-mini", "gpt-5-mini"),
                ("gpt-5-nano", "gpt-5-nano"),
                ("back", "Back"),
            ]
            click.echo()
            model_idx = select(models, title="  Model:", default=0)
            if models[model_idx][0] == "back":
                return
            data["providers"]["openai"]["defaultModel"] = models[model_idx][0]
    else:
        click.echo("  No provider configured.")
        return

    save()
    click.echo("  Saved.")


def _edit_telegram(data: dict, save: Callable[[], None]) -> None:
    """Edit Telegram settings."""
    while True:
        click.echo()
        channels = data.get("channels", {})
        tg = channels.get("telegram", {})

        current_enabled = tg.get("enabled", False)
        current_users = tg.get("allowFrom", [])
        current_token = tg.get("token", "")
        masked_token = current_token[:4] + "****" if current_token else "(not set)"

        click.echo(f"  Enabled: {current_enabled}")
        click.echo(f"  Token: {masked_token}")
        click.echo(f"  Allowed users: {current_users}")
        click.echo()

        options = [
            ("toggle", f"{'Disable' if current_enabled else 'Enable'} Telegram"),
            ("token", "Change bot token"),
            ("users", "Edit allowed users"),
            ("back", "Back"),
        ]
        choice = select(options, title="  Edit:", default=0)

        if choice == 3:  # Back
            return

        if choice == 0:  # Toggle
            tg["enabled"] = not current_enabled
            click.echo(f"  Telegram {'enabled' if tg['enabled'] else 'disabled'}")
        elif choice == 1:  # Token
            click.echo()
            click.echo("  (leave empty to cancel)")
            token = click.prompt("  Bot token", default="", show_default=False)
            if not token:
                click.echo("  Cancelled.")
                continue
            tg["token"] = token
        elif choice == 2:  # Users
            click.echo()
            click.echo("  (leave empty to cancel)")
            users = click.prompt("  Allowed user IDs (comma-separated)", default="", show_default=False)
            if not users:
                click.echo("  Cancelled.")
                continue
            tg["allowFrom"] = [u.strip() for u in users.split(",")]

        if "channels" not in data:
            data["channels"] = {}
        data["channels"]["telegram"] = tg
        save()
        click.echo("  Saved.")


def _edit_tools(data: dict, save: Callable[[], None]) -> None:
    """Edit tools settings."""
    while True:
        click.echo()
        tools = data.get("tools", {})
        web_search = tools.get("webSearch", {})

        current_key = web_search.get("apiKey", "")
        masked_key = current_key[:4] + "****" if current_key else "(not set)"

        click.echo(f"  Brave Search API key: {masked_key}")
        click.echo()

        options = [
            ("brave", "Set Brave Search API key"),
            ("back", "Back"),
        ]
        choice = select(options, title="  Edit:", default=0)

        if choice == 1:  # Back
            return

        if choice == 0:  # Brave key
            click.echo()
            click.echo("  (leave empty to cancel)")
            api_key = click.prompt("  Brave Search API key", default="", show_default=False)
            if not api_key:
                click.echo("  Cancelled.")
                continue
            if "tools" not in data:
                data["tools"] = {}
            if "webSearch" not in data["tools"]:
                data["tools"]["webSearch"] = {}
            data["tools"]["webSearch"]["apiKey"] = api_key
            save()
            click.echo("  Saved.")


def _edit_langfuse(data: dict, save: Callable[[], None]) -> None:
    """Edit Langfuse observability settings."""
    while True:
        click.echo()
        langfuse = data.get("langfuse", {})

        current_enabled = langfuse.get("enabled", False)
        current_public = langfuse.get("publicKey", "")
        current_secret = langfuse.get("secretKey", "")
        current_host = langfuse.get("host", "https://cloud.langfuse.com")

        masked_public = current_public[:8] + "****" if len(current_public) > 12 else "(not set)"
        masked_secret = "****" if current_secret else "(not set)"

        click.echo(f"  Enabled: {current_enabled}")
        click.echo(f"  Public Key: {masked_public}")
        click.echo(f"  Secret Key: {masked_secret}")
        click.echo(f"  Host: {current_host}")
        click.echo()

        options = [
            ("toggle", f"{'Disable' if current_enabled else 'Enable'} Langfuse"),
            ("keys", "Update API keys"),
            ("host", "Update host URL"),
            ("back", "Back"),
        ]
        choice = select(options, title="  Edit:", default=0)

        if choice == 3:  # Back
            return

        if choice == 0:  # Toggle
            if "langfuse" not in data:
                data["langfuse"] = {}
            data["langfuse"]["enabled"] = not current_enabled
            save()
            click.echo(f"  Langfuse {'enabled' if data['langfuse']['enabled'] else 'disabled'}.")

        elif choice == 1:  # Update keys
            click.echo()
            click.echo("  Get keys from: https://cloud.langfuse.com (Settings -> API Keys)")
            click.echo("  (leave empty to cancel)")
            public_key = click.prompt("  Public Key (pk-lf-...)", default="", show_default=False)
            if not public_key:
                click.echo("  Cancelled.")
                continue
            secret_key = click.prompt("  Secret Key (sk-lf-...)", default="", show_default=False)
            if not secret_key:
                click.echo("  Cancelled.")
                continue
            if "langfuse" not in data:
                data["langfuse"] = {}
            data["langfuse"]["publicKey"] = public_key
            data["langfuse"]["secretKey"] = secret_key
            data["langfuse"]["enabled"] = True
            save()
            click.echo("  Saved.")

        elif choice == 2:  # Update host
            click.echo()
            click.echo("  Common hosts:")
            click.echo("    - https://cloud.langfuse.com (EU cloud)")
            click.echo("    - https://us.cloud.langfuse.com (US cloud)")
            click.echo("    - http://localhost:3000 (self-hosted)")
            click.echo("  (leave empty to cancel)")
            host = click.prompt("  Host URL", default=current_host, show_default=True)
            if not host:
                click.echo("  Cancelled.")
                continue
            if "langfuse" not in data:
                data["langfuse"] = {}
            data["langfuse"]["host"] = host
            save()
            click.echo("  Saved.")


if __name__ == "__main__":
    cli()
