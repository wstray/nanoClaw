"""LangChain DeepAgents integration for nanoClaw.

This package provides:
- Tool adapter to convert nanoClaw tools to DeepAgents format
- Safety wrapper to integrate nanoClaw security layers
- Memory adapter to connect nanoClaw memory system
- New Agent implementation based on DeepAgents
"""

from nanoclaw.deepagents.tools_adapter import adapt_nanoclaw_tool, get_all_adapted_tools
from nanoclaw.deepagents.safety_wrapper import SafeDeepAgent
from nanoclaw.deepagents.memory_adapter import build_deepagents_system_prompt

__all__ = [
    "adapt_nanoclaw_tool",
    "get_all_adapted_tools",
    "SafeDeepAgent",
    "build_deepagents_system_prompt",
]
