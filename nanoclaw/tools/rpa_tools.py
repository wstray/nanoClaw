"""Robocorp RPA robot execution tools."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Optional

from nanoclaw.tools.registry import tool
from nanoclaw.core.logger import get_logger
from nanoclaw.core.config import get_config

logger = get_logger(__name__)


def _get_robots_file() -> Path:
    """Get path to robot registry file."""
    config = get_config()
    if config.tools.robocorp.robots_file:
        return Path(config.tools.robocorp.robots_file)
    return Path.home() / ".nanoclaw" / "robots.json"


def _load_registry() -> dict[str, str]:
    """Load robot name -> path mapping from disk."""
    robots_file = _get_robots_file()
    if robots_file.exists():
        try:
            return json.loads(robots_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load robot registry: {e}")
            return {}
    return {}


def _save_registry(registry: dict[str, str]) -> None:
    """Persist robot registry to disk."""
    robots_file = _get_robots_file()
    robots_file.parent.mkdir(parents=True, exist_ok=True)
    robots_file.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


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


def _get_rcc_path() -> str:
    """Get RCC executable path."""
    config = get_config()
    if config.tools.robocorp.rcc_path:
        return config.tools.robocorp.rcc_path

    # Try to find rcc in PATH
    rcc = shutil.which("rcc")
    if rcc:
        return rcc

    return "rcc"


def _validate_robot_path(robot_path: Path) -> tuple[bool, str]:
    """Validate that path contains a valid robot."""
    if not robot_path.exists():
        return False, f"Path does not exist: {robot_path}"

    if not robot_path.is_dir():
        return False, f"Path is not a directory: {robot_path}"

    robot_yaml = robot_path / "robot.yaml"
    if not robot_yaml.exists():
        return False, f"No robot.yaml found in {robot_path}"

    return True, ""


@tool(
    name="rpa_register",
    description="Register a Robocorp robot with a name for later execution.",
    parameters={
        "name": {
            "type": "string",
            "description": "Short name for the robot (e.g., 'invoice-bot', 'scraper')",
        },
        "path": {
            "type": "string",
            "description": "Absolute or relative path to the robot directory (containing robot.yaml)",
        },
    },
)
async def rpa_register(name: str, path: str) -> str:
    """Register a robot name -> path mapping."""
    if not name or not name.strip():
        return "ERROR: Robot name cannot be empty"

    name = name.strip()
    resolved = Path(path).resolve()

    valid, error = _validate_robot_path(resolved)
    if not valid:
        return f"ERROR: {error}"

    registry = _load_registry()
    registry[name] = str(resolved)
    _save_registry(registry)

    logger.info(f"Registered robot '{name}' at {resolved}")
    return f"Registered '{name}' -> {resolved}"


@tool(
    name="rpa_list",
    description="List all registered Robocorp robots with their paths and status",
    parameters={},
)
async def rpa_list() -> str:
    """List all registered robots."""
    registry = _load_registry()
    if not registry:
        return "No robots registered yet. Use rpa_register to add one."

    lines = ["Registered robots:", ""]
    for robot_name, robot_path in sorted(registry.items()):
        path_obj = Path(robot_path)
        exists = path_obj.exists()
        has_yaml = (path_obj / "robot.yaml").exists() if exists else False

        if exists and has_yaml:
            status = "OK"
        elif exists:
            status = "MISSING robot.yaml"
        else:
            status = "PATH NOT FOUND"

        lines.append(f"  {robot_name}")
        lines.append(f"    Path: {robot_path}")
        lines.append(f"    Status: {status}")
        lines.append("")

    return "\n".join(lines)


@tool(
    name="rpa_run",
    description="Run a registered Robocorp robot by name. Use rpa_list to see available robots.",
    parameters={
        "name": {
            "type": "string",
            "description": "Registered robot name (use rpa_list to see all)",
        },
        "task": {
            "type": "string",
            "description": "Optional: specific task to run (if robot has multiple tasks)",
        },
        "variables": {
            "type": "string",
            "description": "Optional: JSON variables to pass, e.g., '{\"url\":\"https://example.com\"}'",
        },
    },
    needs_confirmation=True,
)
async def rpa_run(
    name: str,
    task: str = "",
    variables: str = "",
) -> str:
    """Run a registered robot by name."""
    robot_path = _resolve_robot(name)
    if robot_path is None:
        registry = _load_registry()
        if registry:
            names = ", ".join(sorted(registry.keys()))
            return f"ERROR: Robot '{name}' not found. Registered: {names}"
        return (
            f"ERROR: Robot '{name}' not found. No robots registered. "
            "Use rpa_register first."
        )

    # Validate robot path
    valid, error = _validate_robot_path(robot_path)
    if not valid:
        return f"ERROR: {error}"

    # Check RCC is available
    rcc_path = _get_rcc_path()
    if not shutil.which(rcc_path) and not Path(rcc_path).exists():
        return (
            f"ERROR: 'rcc' not found at '{rcc_path}'. "
            "Install from https://robocorp.com/docs/rcc/installation"
        )

    # Build rcc command
    cmd = [rcc_path, "run", str(robot_path)]
    if task:
        cmd.extend(["--task", task])
    if variables:
        try:
            vars_dict = json.loads(variables)
            if not isinstance(vars_dict, dict):
                return "ERROR: variables must be a JSON object (dictionary)"
            for key, value in vars_dict.items():
                cmd.extend(["--variable", f"{key}:{value}"])
        except json.JSONDecodeError as e:
            return f"ERROR: Invalid JSON in variables: {e}"

    logger.info(f"Running robot '{name}': {' '.join(cmd)}")

    # Get timeout from config
    config = get_config()
    timeout = config.tools.robocorp.default_timeout

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as e:
        return f"ERROR: Failed to start robot: {e}"

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return f"TIMEOUT: Robot execution exceeded {timeout} seconds"

    out = stdout.decode("utf-8", errors="replace")
    err = stderr.decode("utf-8", errors="replace")
    exit_code = process.returncode or 0

    # Build response
    lines = [
        f"Robot: {name}",
        f"Path: {robot_path}",
        f"Exit code: {exit_code}",
        "",
    ]

    if out:
        lines.append("Output:")
        lines.append(out)
        lines.append("")

    if err:
        lines.append("Errors:")
        lines.append(err)
        lines.append("")

    # Parse output.json if generated
    output_json = robot_path / "output" / "output.json"
    if not output_json.exists():
        # Try alternate location
        output_json = robot_path / "output.json"

    if output_json.exists():
        try:
            data = json.loads(output_json.read_text(encoding="utf-8"))
            lines.append("Results:")
            lines.append(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            lines.append(f"Note: Could not parse output.json: {e}")

    return "\n".join(lines)


@tool(
    name="rpa_unregister",
    description="Remove a registered robot from the registry",
    parameters={
        "name": {
            "type": "string",
            "description": "Robot name to remove",
        },
    },
)
async def rpa_unregister(name: str) -> str:
    """Remove a robot from the registry."""
    if not name or not name.strip():
        return "ERROR: Robot name cannot be empty"

    name = name.strip()
    registry = _load_registry()

    if name not in registry:
        return f"Robot '{name}' is not registered."

    del registry[name]
    _save_registry(registry)

    logger.info(f"Unregistered robot '{name}'")
    return f"Removed '{name}' from registry."


def load_config_robots() -> list[str]:
    """Load pre-registered robots from config into registry.

    This function is called on startup to automatically register
    robots defined in the configuration file.

    Returns:
        List of registered robot names.

    Example:
        # In config.json:
        {
            "tools": {
                "robocorp": {
                    "robots": {
                        "invoice-bot": "/path/to/robot"
                    }
                }
            }
        }
    """
    config = get_config()
    config_robots = config.tools.robocorp.robots

    if not config_robots:
        return []

    registry = _load_registry()
    registered = []

    for name, path in config_robots.items():
        # Skip if already registered
        if name in registry:
            continue

        # Validate path
        robot_path = Path(path).resolve()
        valid, error = _validate_robot_path(robot_path)

        if valid:
            registry[name] = str(robot_path)
            registered.append(name)
            logger.info(f"Auto-registered robot '{name}' from config at {robot_path}")
        else:
            logger.warning(f"Failed to auto-register robot '{name}': {error}")

    if registered:
        _save_registry(registry)

    return registered
