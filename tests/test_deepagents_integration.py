"""Tests for LangChain DeepAgents integration."""

from unittest.mock import Mock, AsyncMock, patch


async def test_tools_adapter():
    """Test tool adapter functionality."""
    from nanoclaw.deepagents.tools_adapter import adapt_nanoclaw_tool, get_tool_names

    # Test get_tool_names
    tool_names = get_tool_names()
    assert isinstance(tool_names, list)
    assert len(tool_names) > 0

    # Mock tool info
    mock_tool_info = Mock()
    mock_tool_info.name = "test_tool"
    mock_tool_info.description = "Test tool description"
    mock_tool_info.parameters = {"query": {"type": "string"}}
    mock_tool_info.required_params = ["query"]
    mock_tool_info.needs_confirmation = False

    # Mock registry execute
    with patch("nanoclaw.deepagents.tools_adapter.get_tool_registry") as mock_registry:
        mock_registry_instance = Mock()
        mock_registry_instance.execute = AsyncMock(return_value="test result")
        mock_registry.return_value = mock_registry_instance

        adapted = adapt_nanoclaw_tool(mock_tool_info)

        # Verify structure
        assert adapted["name"] == "test_tool"
        assert adapted["description"] == "Test tool description"
        assert "func" in adapted
        assert "parameters" in adapted

        # Test calling the adapted tool
        result = await adapted["func"](query="test")
        assert result == "test result"


async def test_memory_adapter():
    """Test memory adapter functionality."""
    from nanoclaw.deepagents.memory_adapter import (
        build_deepagents_system_prompt,
        format_history_for_deepagents,
        format_memories_for_prompt,
        get_current_time,
    )

    # Test get_current_time
    time_str = get_current_time()
    assert isinstance(time_str, str)
    assert len(time_str) > 0

    # Test format_history_for_deepagents
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    formatted = format_history_for_deepagents(history)
    assert isinstance(formatted, list)
    assert len(formatted) == 2
    assert formatted[0]["role"] == "user"

    # Test format_memories_for_prompt
    memories = [
        {"content": "User name is John", "category": "personal"},
        {"content": "User is a developer", "category": "work"},
    ]
    memory_text = format_memories_for_prompt(memories)
    assert "John" in memory_text
    assert "developer" in memory_text

    # Test build_deepagents_system_prompt
    with patch("nanoclaw.deepagents.memory_adapter.get_logger") as mock_logger:
        mock_memory = AsyncMock()
        mock_memory.get_history = AsyncMock(return_value=[])
        mock_memory.search_memories = AsyncMock(return_value=[])

        mock_ctx = Mock()
        mock_ctx.build_system_prompt = Mock(return_value="Base prompt")

        prompt = await build_deepagents_system_prompt(
            "Test message",
            "test_session",
            mock_memory,
            mock_ctx,
            enable_planning=True,
            enable_subagents=True,
        )

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "DEEPAGENTS" in prompt or "Base prompt" in prompt


def test_config_deepagents():
    """Test DeepAgents configuration."""
    from nanoclaw.core.config import DeepAgentsConfig, AgentConfig

    # Test default values
    deepagents_config = DeepAgentsConfig()
    assert deepagents_config.enabled is True
    assert deepagents_config.enable_planning is True
    assert deepagents_config.enable_subagents is True
    assert deepagents_config.tavily_api_key == ""

    # Test with agent config
    agent_config = AgentConfig()
    assert hasattr(agent_config, "deepagents")
    assert agent_config.deepagents.enabled is True


async def test_safety_wrapper_budget():
    """Test safety wrapper budget checking."""
    from nanoclaw.deepagents.safety_wrapper import SafeDeepAgent
    from nanoclaw.security.budget import SessionBudget

    # Mock dependencies
    mock_agent = Mock()
    mock_audit = AsyncMock()
    mock_budget = Mock(spec=SessionBudget)
    mock_budget.check_iteration = Mock(return_value=(False, "Budget exceeded"))
    mock_prompt_guard = Mock()

    wrapper = SafeDeepAgent(
        deepagent_instance=mock_agent,
        audit=mock_audit,
        budget=mock_budget,
        prompt_guard=mock_prompt_guard,
    )

    # Test budget check
    result = await wrapper.invoke(
        {"messages": [{"role": "user", "content": "test"}]},
        "test_session",
    )

    # Should be blocked by budget
    assert "Stopped" in result["messages"][0]["content"]
    assert "Budget exceeded" in result["messages"][0]["content"]


if __name__ == "__main__":
    # Run tests manually for quick verification
    import asyncio

    print("Running tests...")

    # Test 1: Tool adapter
    print("\n1. Testing tool adapter...")
    asyncio.run(test_tools_adapter())
    print("[OK] Tool adapter tests passed")

    # Test 2: Memory adapter
    print("\n2. Testing memory adapter...")
    asyncio.run(test_memory_adapter())
    print("[OK] Memory adapter tests passed")

    # Test 3: Config
    print("\n3. Testing DeepAgents config...")
    test_config_deepagents()
    print("[OK] Config tests passed")

    # Test 4: Safety wrapper
    print("\n4. Testing safety wrapper...")
    asyncio.run(test_safety_wrapper_budget())
    print("[OK] Safety wrapper tests passed")

    print("\n[SUCCESS] All tests passed!")
