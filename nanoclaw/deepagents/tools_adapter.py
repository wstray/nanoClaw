"""Tool adapter to convert nanoClaw tools to DeepAgents format."""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from nanoclaw.core.logger import get_logger
from nanoclaw.tools.registry import ToolInfo, get_tool_registry

logger = get_logger(__name__)


def adapt_nanoclaw_tool(
    tool_info: ToolInfo,
    confirm_callback: Optional[Callable] = None,
):
    """
    Convert a nanoClaw ToolInfo to DeepAgents Tool format.

    Args:
        tool_info: nanoClaw tool information
        confirm_callback: Optional callback for user confirmation

    Returns:
        DeepAgents-compatible tool dictionary
    """
    async def wrapper(**kwargs) -> str:
        """Execute the nanoClaw tool."""
        registry = get_tool_registry()

        # Handle confirmation
        if tool_info.needs_confirmation and confirm_callback:
            approved = await confirm_callback(
                f"Tool `{tool_info.name}` wants to run with:\n"
                f"```\n{json.dumps(kwargs, indent=2)}\n```\n\nAllow?"
            )
            if not approved:
                return f"Tool {tool_info.name} was denied by user."

        # Execute tool through nanoClaw registry
        try:
            result = await registry.execute(tool_info.name, kwargs)
            return str(result)
        except Exception as e:
            logger.error(f"Tool {tool_info.name} failed: {e}")
            return f"ERROR: {tool_info.name} failed - {e}"

    # Build DeepAgents tool schema
    # Note: DeepAgents expects a specific format similar to OpenAI function calling
    adapted_tool = {
        "name": tool_info.name,
        "description": tool_info.description,
        "func": wrapper,
        "parameters": {
            "type": "object",
            "properties": tool_info.parameters,
            "required": tool_info.required_params,
        },
    }

    return adapted_tool


def get_all_adapted_tools(confirm_callback: Optional[Callable] = None) -> list[dict]:
    """
    Get all nanoClaw tools adapted for DeepAgents.

    Args:
        confirm_callback: Optional callback for tools requiring confirmation

    Returns:
        List of DeepAgents-compatible tool dictionaries
    """
    registry = get_tool_registry()
    adapted_tools = []

    for tool_name, tool_info in registry.tools.items():
        try:
            adapted = adapt_nanoclaw_tool(tool_info, confirm_callback)
            adapted_tools.append(adapted)
            logger.debug(f"Adapted tool: {tool_name}")
        except Exception as e:
            logger.error(f"Failed to adapt tool {tool_name}: {e}")

    logger.info(f"Adapted {len(adapted_tools)} tools for DeepAgents")
    return adapted_tools


def get_tool_names() -> list[str]:
    """Get list of all available tool names."""
    registry = get_tool_registry()
    return list(registry.tools.keys())
