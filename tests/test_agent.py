"""Agent loop tests."""

from __future__ import annotations

import copy
from typing import Any, Optional

import pytest

from nanoclaw.core.agent import Agent
from nanoclaw.core.context import ContextBuilder
from nanoclaw.core.llm import LLMResponse, TokenUsage, ToolCall
from nanoclaw.security.budget import SessionBudget
from nanoclaw.security.prompt_guard import PromptGuard


class FakeLLM:
    """Deterministic LLM stub for agent tests."""

    def __init__(self) -> None:
        self.calls = 0
        self.seen_messages: list[list[dict[str, Any]]] = []

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Return a tool call on the first call, and final text on the second."""
        self.calls += 1
        self.seen_messages.append(copy.deepcopy(messages))

        if self.calls == 1:
            return LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="web_search",
                        arguments={"query": "hello"},
                    )
                ],
                usage=TokenUsage(prompt_tokens=5, completion_tokens=5),
            )

        return LLMResponse(
            content="done",
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=5, completion_tokens=5),
        )


class FakeToolRegistry:
    """Minimal tool registry stub."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, Any]]] = []

    def get_schemas(self) -> list[dict[str, Any]]:
        """Return a single core tool schema."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Fake search tool",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query",
                            }
                        },
                        "required": ["query"],
                    },
                },
            }
        ]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        confirm_callback: Optional[Any] = None,
    ) -> str:
        """Record tool execution and return a result."""
        self.executed.append((name, arguments))
        return "search result"


class FakeMemoryStore:
    """In-memory memory store stub."""

    def __init__(self) -> None:
        self.history: list[dict[str, Any]] = []
        self.memories: list[dict[str, Any]] = []

    async def get_history(self, session_id: str, limit: int = 15) -> list[dict]:
        """Return stored history."""
        return self.history[-limit:]

    async def search_memories(self, query: str, limit: int = 5) -> list[dict]:
        """Return no memories by default."""
        return []

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_name: Optional[str] = None,
    ) -> None:
        """Store a message."""
        self.history.append(
            {
                "session_id": session_id,
                "role": role,
                "content": content,
                "tool_name": tool_name,
            }
        )

    async def save_memory(self, content: str, category: str = "auto") -> None:
        """Store a memory fact."""
        self.memories.append({"content": content, "category": category})


class FakeAuditLog:
    """Audit log stub for tests."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    async def log(self, **kwargs: Any) -> None:
        """Record audit entries."""
        self.entries.append(kwargs)


@pytest.mark.asyncio
async def test_agent_executes_tool_and_returns_response() -> None:
    """Agent should execute tool calls and return final response."""
    llm = FakeLLM()
    memory = FakeMemoryStore()
    tools = FakeToolRegistry()
    audit = FakeAuditLog()
    budget = SessionBudget(max_iterations=5)
    prompt_guard = PromptGuard()
    agent = Agent(
        llm=llm,
        memory=memory,
        tools=tools,
        audit=audit,
        budget=budget,
        prompt_guard=prompt_guard,
        context_builder=ContextBuilder(),
        max_iterations=5,
    )

    result = await agent.run("search please", session_id="s1")
    assert result == "done"
    assert tools.executed == [("web_search", {"query": "hello"})]

    tool_msgs = [
        m for m in llm.seen_messages[1] if m.get("role") == "tool"
    ]
    assert tool_msgs
    assert "<tool_result" in tool_msgs[0]["content"]
    assert memory.history[0]["role"] == "user"


def test_get_platform_default_path_windows() -> None:
    """Platform default PATH should include System32 on Windows."""
    import sys
    from nanoclaw.core.agent import get_platform_default_path

    # Mock Windows platform
    original_platform = sys.platform
    sys.platform = "win32"

    try:
        path = get_platform_default_path()
        assert "System32" in path
        assert ";" in path  # Windows separator
    finally:
        sys.platform = original_platform


def test_get_platform_default_path_unix() -> None:
    """Platform default PATH should include /usr/bin on Unix."""
    import sys
    from nanoclaw.core.agent import get_platform_default_path

    # Mock Unix platform
    original_platform = sys.platform
    sys.platform = "linux"

    try:
        path = get_platform_default_path()
        assert "/usr/bin" in path
        assert ":" in path  # Unix separator
    finally:
        sys.platform = original_platform
