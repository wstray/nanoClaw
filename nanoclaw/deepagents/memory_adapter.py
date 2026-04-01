"""Memory adapter to connect nanoClaw memory system with DeepAgents."""

from __future__ import annotations

from datetime import datetime

from nanoclaw.core.context import ContextBuilder
from nanoclaw.core.logger import get_logger
from nanoclaw.memory.store import MemoryStore

logger = get_logger(__name__)


async def build_deepagents_system_prompt(
    user_message: str,
    session_id: str,
    memory: MemoryStore,
    ctx: ContextBuilder,
    enable_planning: bool = True,
    enable_subagents: bool = True,
) -> str:
    """
    Build system prompt for DeepAgents with nanoClaw memory and context.

    Args:
        user_message: Current user message
        session_id: Session identifier
        memory: nanoClaw memory store
        ctx: nanoClaw context builder
        enable_planning: Enable DeepAgents planning capabilities
        enable_subagents: Enable DeepAgents subagent delegation

    Returns:
        System prompt string for DeepAgents
    """
    # Load conversation history and relevant memories
    history = await memory.get_history(session_id, limit=15)
    relevant_memories = await memory.search_memories(user_message, limit=5)

    # Use existing ContextBuilder to build base prompt
    base_prompt = ctx.build_system_prompt(relevant_memories)

    # Add DeepAgents-specific capabilities
    capabilities_section = _build_capabilities_section(
        enable_planning, enable_subagents
    )

    # Combine base prompt with DeepAgents enhancements
    enhanced_prompt = f"""{base_prompt}

{capabilities_section}

DEEPAGENTS INSTRUCTIONS:
1. You have access to advanced planning tools (write_todos)
2. Break complex tasks into clear steps before executing
3. Use file system tools (write_file, read_file) to manage large context
4. Spawn subagents for independent subtasks when beneficial
5. Always provide a clear final summary to the user
6. Be concise - avoid unnecessary iterations

WORKFLOW:
- For simple queries: Answer directly using available tools
- For complex tasks: Plan first, then execute step by step
- For research: Use search tools, compile findings, summarize
- For multi-step tasks: Use write_todos to track progress
"""

    return enhanced_prompt


def _build_capabilities_section(
    enable_planning: bool, enable_subagents: bool
) -> str:
    """Build the capabilities section based on enabled features."""
    capabilities = []

    if enable_planning:
        capabilities.append("- Automatic task planning and decomposition")
        capabilities.append("- Progress tracking with write_todos")

    if enable_subagents:
        capabilities.append("- Subagent spawning for specialized tasks")

    if not capabilities:
        return ""

    return f"""DEEPAGENTS CAPABILITIES:
{chr(10).join(capabilities)}"""


async def extract_and_save_memories(
    user_message: str,
    assistant_response: str,
    memory: MemoryStore,
) -> None:
    """
    Extract important facts from conversation and save to memory.

    This integrates nanoClaw's memory extraction with DeepAgents conversations.

    Args:
        user_message: User's message
        assistant_response: Agent's response
        memory: Memory store to save to
    """
    # Skip short messages
    if len(user_message) < 20:
        return

    # Triggers for memory extraction
    triggers = [
        "my name",
        "i work",
        "i live",
        "i prefer",
        "i like",
        "i am",
        "my job",
        "i'm",
        "remember that",
        "don't forget",
        "i need",
        "my project",
        "my company",
        "my team",
    ]

    should_extract = any(t in user_message.lower() for t in triggers)
    if not should_extract:
        return

    # Note: In a full implementation, we would call the LLM here
    # to extract facts. For now, we'll skip to avoid extra complexity.
    # The existing Agent class has this logic, so we can defer to it.

    logger.debug("Memory extraction triggered (implementation deferred to Agent)")


def format_history_for_deepagents(history: list[dict]) -> list[dict]:
    """
    Format nanoClaw history for DeepAgents consumption.

    Args:
        history: List of history dicts with role and content

    Returns:
        Formatted history for DeepAgents
    """
    formatted = []

    for msg in history:
        if not isinstance(msg, dict):
            continue

        # Map roles
        role = msg.get("role", "user")
        if role == "assistant":
            role = "assistant"  # DeepAgents uses "assistant"

        formatted.append({
            "role": role,
            "content": msg.get("content", ""),
        })

    return formatted


def format_memories_for_prompt(memories: list[dict]) -> str:
    """
    Format retrieved memories for inclusion in system prompt.

    Args:
        memories: List of memory dicts

    Returns:
        Formatted memory string
    """
    if not memories:
        return ""

    facts = []
    for mem in memories[:5]:  # Limit to top 5
        content = mem.get("content", "")
        category = mem.get("category", "general")
        facts.append(f"- [{category}] {content}")

    if not facts:
        return ""

    return f"""Known about user:
{chr(10).join(facts)}"""


def get_current_time() -> str:
    """Get current time formatted for prompts."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
