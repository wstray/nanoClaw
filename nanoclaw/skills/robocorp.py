"""Robocorp RPA robot execution skill with name-based registry."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from nanoclaw.tools.registry import tool
from nanoclaw.core.logger import get_logger

logger = get_logger(__name__)

# Robot registry file: ~/.nanoclaw/robots.json
# Format: {"name": "/absolute/path", ...}
_ROBOTS_FILE = Path.home() / ".nanoclaw" / "robots.json"


def _load_registry() -> dict[str, str]:
    """Load robot name -> path mapping from disk."""
    if _ROBOTS_FILE.exists():
        try:
            return json.loads(_ROBOTS_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_registry(registry: dict[str, str]) -> None:
    """Persist robot registry to disk."""
    _ROBOTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ROBOTS_FILE.write_text(json.dumps(registry, indent=2, ensure_ascii=False))


def _resolve_robot(name_or_path: str) -> Path | None:
    """Resolve a robot by registered name, or fall back to direct path."""
    # 1. Try registry lookup
    registry = _load_registry()
    if name_or_path in registry:
        return Path(registry[name_or_path])

    # 2. Try as direct path
    p = Path(name_or_path)
    if p.exists():
        return p

    return None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool(
    name="robocorp_register",
    description="Register a robot with a short name so you can run it by name later. Only needs to be done once per robot.",
    parameters={
        "name": {
            "type": "string",
            "description": "Short name for the robot (e.g. 'scraper', 'invoice-bot')",
        },
        "path": {
            "type": "string",
            "description": "Absolute or relative path to the robot directory (containing robot.yaml)",
        },
    },
)
async def robocorp_register(name: str, path: str) -> str:
    """Register a robot name -> path mapping."""
    resolved = Path(path).resolve()
    if not resolved.exists():
        return f"ERROR: Path not found: {resolved}"

    registry = _load_registry()
    registry[name] = str(resolved)
    _save_registry(registry)
    return f"Registered '{name}' -> {resolved}"


@tool(
    name="robocorp_list",
    description="List all registered robots and their paths",
    parameters={},
)
async def robocorp_list() -> str:
    """List all registered robots."""
    registry = _load_registry()
    if not registry:
        return "No robots registered yet. Use robocorp_register to add one."

    lines = ["Registered robots:"]
    for name, path in registry.items():
        exists = "OK" if Path(path).exists() else "MISSING"
        lines.append(f"  {name} -> {path} [{exists}]")
    return "\n".join(lines)


@tool(
    name="robocorp_run",
    description="Run a registered robot by name. Use robocorp_list to see available names.",
    parameters={
        "name": {
            "type": "string",
            "description": "Registered robot name (use robocorp_list to see all)",
        },
        "task": {
            "type": "string",
            "description": "Optional: specific task to run (if robot has multiple tasks)",
        },
        "variables": {
            "type": "string",
            "description": "Optional: JSON variables to pass, e.g. '{\"url\":\"https://example.com\"}'",
        },
    },
    needs_confirmation=True,
)
async def robocorp_run(
    name: str,
    task: str = "",
    variables: str = "",
) -> str:
    """Run a registered robot by name."""
    robot_path = _resolve_robot(name)
    if robot_path is None:
        registry = _load_registry()
        if registry:
            names = ", ".join(registry.keys())
            return f"ERROR: Robot '{name}' not found. Registered: {names}"
        return f"ERROR: Robot '{name}' not found and no robots registered. Use robocorp_register first."

    # Build rcc command
    cmd = ["rcc", "run", str(robot_path)]
    if task:
        cmd.extend(["--task", task])
    if variables:
        try:
            vars_dict = json.loads(variables)
            cmd.extend(["--variable", json.dumps(vars_dict)])
        except json.JSONDecodeError as e:
            return f"ERROR: Invalid JSON in variables: {e}"

    logger.info(f"Running robot '{name}': {' '.join(cmd)}")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return "ERROR: 'rcc' not found. Install from https://robocorp.com/docs/rcc/installation"

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=300
        )
    except asyncio.TimeoutError:
        process.kill()
        return "TIMEOUT: Robot execution exceeded 5 minutes"

    out = stdout.decode("utf-8", errors="replace")
    err = stderr.decode("utf-8", errors="replace")
    exit_code = process.returncode or 0

    response = f"Robot: {name}\nExit code: {exit_code}\n"
    if out:
        response += f"Output:\n{out}\n"
    if err:
        response += f"Errors:\n{err}\n"

    # Parse output.json if generated
    output_json = robot_path / "output" / "output.json"
    if not output_json.exists():
        output_json = Path("output.json")
    if output_json.exists():
        try:
            data = json.loads(output_json.read_text())
            response += f"Results:\n{json.dumps(data, indent=2, ensure_ascii=False)}"
        except Exception:
            pass

    return response


@tool(
    name="robocorp_unregister",
    description="Remove a registered robot by name",
    parameters={
        "name": {
            "type": "string",
            "description": "Robot name to remove",
        },
    },
)
async def robocorp_unregister(name: str) -> str:
    """Remove a robot from the registry."""
    registry = _load_registry()
    if name not in registry:
        return f"Robot '{name}' is not registered."
    del registry[name]
    _save_registry(registry)
    return f"Removed '{name}'."
