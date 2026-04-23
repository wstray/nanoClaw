"""Tool registration system with decorator-based discovery."""

from __future__ import annotations

import importlib
import importlib.util
import os
import stat
import sys
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional

from nanoclaw.core.jsonl_logger import ToolCallStatus, get_jsonl_logger
from nanoclaw.core.logger import get_logger

logger = get_logger(__name__)


def _get_current_uid() -> int:
    """Get current user ID, with Windows compatibility."""
    if sys.platform == "win32":
        return 0  # Windows doesn't have UID, return 0 to skip check
    return _get_current_uid()


@dataclass
class ToolInfo:
    """Information about a registered tool."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable
    needs_confirmation: bool = False
    required_params: list[str] = field(default_factory=list)


# Global tool registry
_registry: dict[str, ToolInfo] = {}
_core_tools_loaded = False

_CORE_TOOL_MODULES = (
    "nanoclaw.tools.files",
    "nanoclaw.tools.memory_tools",
    "nanoclaw.tools.rpa_tools",
    "nanoclaw.tools.shell",
    "nanoclaw.tools.spawn",
    "nanoclaw.tools.web",
)

_CORE_TOOL_NAMES = {
    "file_read",
    "file_write",
    "file_list",
    "shell_exec",
    "web_search",
    "web_fetch",
    "memory_save",
    "memory_search",
    "spawn_task",
    "rpa_register",
    "rpa_list",
    "rpa_run",
    "rpa_unregister",
}


def _core_tools_present() -> bool:
    """Check if all core tools are registered."""
    return _CORE_TOOL_NAMES.issubset(_registry.keys())


def _load_core_tools() -> None:
    """Ensure core tool modules are imported and registered."""
    global _core_tools_loaded
    if _core_tools_loaded and _core_tools_present():
        return

    needs_reload = not _core_tools_present()
    for module_name in _CORE_TOOL_MODULES:
        try:
            if needs_reload and module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
        except Exception as e:
            logger.error(f"Failed to load core tool module {module_name}: {e}")

    _core_tools_loaded = True


def tool(
    name: str,
    description: str,
    parameters: dict[str, Any],
    needs_confirmation: bool = False,
    required: Optional[list[str]] = None,
) -> Callable:
    """
    Decorator to register a tool.

    Args:
        name: Tool name (used in LLM tool_calls)
        description: Human-readable description for LLM
        parameters: JSON Schema for parameters
        needs_confirmation: If True, always asks user before executing
        required: List of required parameter names (defaults to all)

    Example:
        @tool(
            name="web_search",
            description="Search the internet",
            parameters={"query": {"type": "string", "description": "Search query"}}
        )
        async def web_search(query: str) -> str:
            ...
    """

    def decorator(func: Callable) -> Callable:
        req_params = required if required is not None else list(parameters.keys())
        _registry[name] = ToolInfo(
            name=name,
            description=description,
            parameters=parameters,
            handler=func,
            needs_confirmation=needs_confirmation,
            required_params=req_params,
        )
        if _tool_registry is not None:
            _tool_registry.tools[name] = _registry[name]

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)

        return wrapper

    return decorator


class ToolRegistry:
    """Registry for managing and executing tools."""

    def __init__(self) -> None:
        """Initialize with copy of global registry."""
        self.tools: dict[str, ToolInfo] = dict(_registry)

    def get_schemas(self) -> list[dict[str, Any]]:
        """
        Generate OpenAI-compatible tool schemas for LLM.

        Returns:
            List of tool schemas in OpenAI format
        """
        schemas = []
        for name, info in self.tools.items():
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": info.name,
                        "description": info.description,
                        "parameters": {
                            "type": "object",
                            "properties": info.parameters,
                            "required": info.required_params,
                        },
                    },
                }
            )
        return schemas

    def get_tool_names(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self.tools.keys())

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        confirm_callback: Optional[Callable] = None,
    ) -> str:
        """
        Execute a tool by name with given arguments.

        Args:
            name: Tool name
            arguments: Tool arguments
            confirm_callback: Optional async callback for user confirmation

        Returns:
            Tool result as string
        """
        if name not in self.tools:
            return f"Unknown tool: {name}"

        tool_info = self.tools[name]
        jsonl_logger = get_jsonl_logger()

        # Extract session_id from arguments if present
        session_id = arguments.get("_session_id", "unknown")
        tool_id = arguments.get("_tool_id", f"{name}-{id(arguments)}")

        # Remove internal arguments
        clean_arguments = {k: v for k, v in arguments.items() if not k.startswith("_")}

        import time
        start_time = time.time()
        confirmation_granted = False

        # Log tool call start
        if jsonl_logger:
            await jsonl_logger.log_tool_call(
                session_id=session_id,
                tool_name=name,
                tool_id=tool_id,
                parameters=clean_arguments,
                result="",
                status=ToolCallStatus.RUNNING,
                duration_ms=0,
                requires_confirmation=tool_info.needs_confirmation,
                confirmation_granted=False
            )

        # Tools that always need confirmation
        if tool_info.needs_confirmation and confirm_callback:
            import json

            approved = await confirm_callback(
                f"Tool `{name}` wants to run with:\n"
                f"```\n{json.dumps(arguments, indent=2)}\n```\n\nAllow?"
            )
            if not approved:
                # Log denied confirmation
                if jsonl_logger:
                    elapsed = time.time() - start_time
                    await jsonl_logger.log_tool_call(
                        session_id=session_id,
                        tool_name=name,
                        tool_id=tool_id,
                        parameters=clean_arguments,
                        result="User denied this action",
                        status=ToolCallStatus.BLOCKED,
                        duration_ms=int(elapsed * 1000),
                        requires_confirmation=True,
                        confirmation_granted=False
                    )
                return "User denied this action."

            confirmation_granted = True

        try:
            # Handle malformed LLM output: {'parameters': {'query': '...'}}
            if "parameters" in arguments and len(arguments) == 1:
                logger.warning(f"Tool {name}: unwrapping nested 'parameters' from LLM")
                arguments = arguments["parameters"]

            result = await tool_info.handler(**arguments)
            elapsed = time.time() - start_time

            # Log successful tool call
            if jsonl_logger:
                await jsonl_logger.log_tool_call(
                    session_id=session_id,
                    tool_name=name,
                    tool_id=tool_id,
                    parameters=clean_arguments,
                    result=str(result)[:1000],  # Truncate large results
                    status=ToolCallStatus.SUCCESS,
                    duration_ms=int(elapsed * 1000),
                    requires_confirmation=tool_info.needs_confirmation,
                    confirmation_granted=confirmation_granted
                )

            return str(result)
        except TypeError as e:
            elapsed = time.time() - start_time
            error_msg = f"Invalid arguments for {name}: {e}"

            # Log error
            if jsonl_logger:
                await jsonl_logger.log_tool_call(
                    session_id=session_id,
                    tool_name=name,
                    tool_id=tool_id,
                    parameters=clean_arguments,
                    result=error_msg,
                    status=ToolCallStatus.ERROR,
                    duration_ms=int(elapsed * 1000),
                    requires_confirmation=tool_info.needs_confirmation,
                    confirmation_granted=confirmation_granted
                )

            return error_msg
        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = f"Tool {name} failed: {e}"

            # Log error
            if jsonl_logger:
                await jsonl_logger.log_tool_call(
                    session_id=session_id,
                    tool_name=name,
                    tool_id=tool_id,
                    parameters=clean_arguments,
                    result=error_msg,
                    status=ToolCallStatus.ERROR,
                    duration_ms=int(elapsed * 1000),
                    requires_confirmation=tool_info.needs_confirmation,
                    confirmation_granted=confirmation_granted
                )

            return error_msg

    def load_skills(self, skills_dir: str) -> None:
        """
        Auto-discover and load .py files from skills directory.

        Only loads files owned by the current user and not writable by
        group/others (prevents tampering by other users on shared systems).

        Args:
            skills_dir: Path to skills directory
        """
        skills_path = Path(skills_dir)
        if not skills_path.exists():
            logger.debug(f"Skills directory not found: {skills_dir}")
            return

        # Check directory ownership and permissions (skip on Windows)
        if sys.platform != "win32":
            try:
                dir_stat = skills_path.stat()
                if dir_stat.st_uid != _get_current_uid():
                    logger.warning(f"Skills directory not owned by current user: {skills_dir}")
                    return
                if dir_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                    logger.warning(f"Skills directory writable by others: {skills_dir}")
                    return
            except OSError:
                return

        for py_file in skills_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            # Validate file ownership and permissions (skip on Windows)
            if sys.platform != "win32":
                try:
                    file_stat = py_file.stat()
                    if file_stat.st_uid != _get_current_uid():
                        logger.warning(f"Skipping skill {py_file.name}: not owned by current user")
                        continue
                    if file_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                        logger.warning(f"Skipping skill {py_file.name}: writable by group/others")
                        continue
                except OSError:
                    continue

            try:
                spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    logger.debug(f"Loaded skill: {py_file.name}")
            except Exception as e:
                logger.error(f"Failed to load skill {py_file.name}: {e}")

        # Merge newly loaded tools
        self.tools.update(_registry)

    def register(self, tool_info: ToolInfo) -> None:
        """Manually register a tool."""
        self.tools[tool_info.name] = tool_info
        _registry[tool_info.name] = tool_info


# Global registry instance
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    global _tool_registry
    _load_core_tools()
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    else:
        _tool_registry.tools.update(_registry)
    return _tool_registry


def reset_registry() -> None:
    """Reset the global registry (useful for testing)."""
    global _tool_registry, _registry, _core_tools_loaded
    _registry.clear()
    _tool_registry = None
    _core_tools_loaded = False
