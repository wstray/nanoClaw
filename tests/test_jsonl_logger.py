"""Test JSONL logger functionality."""

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from nanoclaw.core.jsonl_logger import (
    JSONLLogger,
    JSONLLoggerConfig,
    ThoughtType,
    ToolCallStatus,
    LogLevel,
)


@pytest.fixture
def temp_logger():
    """Create a temporary logger for testing."""
    with TemporaryDirectory() as tmp_dir:
        config = JSONLLoggerConfig(
            enabled=True,
            buffer_size=1,  # Flush immediately for testing
        )
        logger = JSONLLogger(
            log_dir=Path(tmp_dir),
            config=config,
            log_name="test",
        )
        yield logger
        # Cleanup
        asyncio.run(logger.close())


@pytest.mark.asyncio
async def test_log_user_message(temp_logger):
    """Test logging user messages."""
    await temp_logger.log_user_message(
        session_id="test:123",
        channel_id="test",
        user_id="123",
        content="Hello world",
    )

    await temp_logger._flush_buffer()

    # Query logs
    entries = await temp_logger.query(filters={"log_type": "user_message"})
    assert len(entries) == 1
    assert entries[0]["content"] == "Hello world"
    assert entries[0]["session_id"] == "test:123"
    assert entries[0]["channel_id"] == "test"
    assert entries[0]["user_id"] == "123"


@pytest.mark.asyncio
async def test_log_agent_response(temp_logger):
    """Test logging agent responses."""
    await temp_logger.log_agent_response(
        session_id="test:123",
        content="Response text",
        tokens_used=100,
        iterations=2,
        tool_calls_count=3,
        duration_ms=1500,
    )

    await temp_logger._flush_buffer()

    entries = await temp_logger.query(filters={"log_type": "agent_response"})
    assert len(entries) == 1
    assert entries[0]["content"] == "Response text"
    assert entries[0]["tokens_used"] == 100
    assert entries[0]["iterations"] == 2
    assert entries[0]["tool_calls_count"] == 3
    assert entries[0]["duration_ms"] == 1500


@pytest.mark.asyncio
async def test_log_agent_thinking(temp_logger):
    """Test logging agent thinking."""
    await temp_logger.log_agent_thinking(
        session_id="test:123",
        iteration=1,
        thought_type=ThoughtType.TOOL_SELECTION,
        content="Selecting web_search tool",
        context={"tools": ["web_search", "web_fetch"]},
    )

    await temp_logger._flush_buffer()

    entries = await temp_logger.query(filters={"log_type": "agent_thinking"})
    assert len(entries) == 1
    assert entries[0]["thought_type"] == "tool_selection"
    assert entries[0]["iteration"] == 1
    assert entries[0]["content"] == "Selecting web_search tool"
    assert "tools" in entries[0]["context"]


@pytest.mark.asyncio
async def test_log_tool_call(temp_logger):
    """Test logging tool calls."""
    await temp_logger.log_tool_call(
        session_id="test:123",
        tool_name="web_search",
        tool_id="tool-123",
        parameters={"query": "test"},
        result="Search results",
        status=ToolCallStatus.SUCCESS,
        duration_ms=500,
        requires_confirmation=False,
        confirmation_granted=False,
    )

    await temp_logger._flush_buffer()

    entries = await temp_logger.query(filters={"log_type": "tool_call"})
    assert len(entries) == 1
    assert entries[0]["tool_name"] == "web_search"
    assert entries[0]["status"] == "success"
    assert entries[0]["duration_ms"] == 500
    assert entries[0]["parameters"]["query"] == "test"


@pytest.mark.asyncio
async def test_log_system(temp_logger):
    """Test logging system messages."""
    await temp_logger.log_system(
        level=LogLevel.ERROR,
        component="test_component",
        message="Test error message",
        exception="Test exception",
        context={"function": "test_func", "line": 42},
    )

    await temp_logger._flush_buffer()

    entries = await temp_logger.query(filters={"log_type": "system_log"})
    assert len(entries) == 1
    assert entries[0]["level"] == "ERROR"
    assert entries[0]["component"] == "test_component"
    assert entries[0]["message"] == "Test error message"
    assert entries[0]["exception"] == "Test exception"


@pytest.mark.asyncio
async def test_query_filters(temp_logger):
    """Test query filtering."""
    await temp_logger.log_user_message("session1", "test", "123", "Message 1")
    await temp_logger.log_user_message("session2", "test", "456", "Message 2")
    await temp_logger.log_user_message("session1", "test", "123", "Message 3")

    await temp_logger._flush_buffer()

    # Query by session_id
    results = await temp_logger.query(filters={"session_id": "session1"})
    assert len(results) == 2

    # Query by user_id
    results = await temp_logger.query(filters={"user_id": "456"})
    assert len(results) == 1


@pytest.mark.asyncio
async def test_get_session_history(temp_logger):
    """Test getting session history."""
    session_id = "test:123"
    await temp_logger.log_user_message(session_id, "test", "123", "Message 1")
    await temp_logger.log_agent_response(session_id, "Response 1")
    await temp_logger.log_agent_thinking(
        session_id, 1, ThoughtType.REASONING, "Thinking"
    )

    await temp_logger._flush_buffer()

    history = await temp_logger.get_session_history(session_id)
    assert len(history) == 3


@pytest.mark.asyncio
async def test_get_tool_stats(temp_logger):
    """Test getting tool statistics."""
    await temp_logger.log_tool_call(
        "test:123", "web_search", "tool-1", {"query": "test"}, "result", ToolCallStatus.SUCCESS, 100
    )
    await temp_logger.log_tool_call(
        "test:123", "web_search", "tool-2", {"query": "test2"}, "result2", ToolCallStatus.SUCCESS, 200
    )
    await temp_logger.log_tool_call(
        "test:123", "shell_exec", "tool-3", {"command": "ls"}, "output", ToolCallStatus.ERROR, 50
    )

    await temp_logger._flush_buffer()

    stats = await temp_logger.get_tool_stats()
    assert stats["total_calls"] == 3
    assert stats["successful"] == 2
    assert stats["errors"] == 1
    assert "web_search" in stats["by_tool"]
    assert "shell_exec" in stats["by_tool"]


@pytest.mark.asyncio
async def test_export_json(temp_logger):
    """Test exporting logs as JSON."""
    await temp_logger.log_user_message("test:123", "test", "123", "Test message")

    await temp_logger._flush_buffer()

    json_export = await temp_logger.export(format="json")
    data = json.loads(json_export)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["log_type"] == "user_message"


@pytest.mark.asyncio
async def test_buffer_flushing(temp_logger):
    """Test buffer flushing."""
    config = JSONLLoggerConfig(enabled=True, buffer_size=5)
    logger = JSONLLogger(
        log_dir=temp_logger.log_dir, config=config, log_name="test_buffer"
    )

    # Add 4 entries - should not flush yet
    for i in range(4):
        await logger.log_system(
            LogLevel.INFO, "test", f"Message {i}", context={"index": i}
        )

    # Manually flush
    await logger._flush_buffer()

    # Check that entries were written
    entries = await logger.query()
    assert len(entries) == 4

    await logger.close()


@pytest.mark.asyncio
async def test_disabled_logger():
    """Test that disabled logger doesn't create logs."""
    with TemporaryDirectory() as tmp_dir:
        config = JSONLLoggerConfig(enabled=False)
        logger = JSONLLogger(
            log_dir=Path(tmp_dir), config=config, log_name="test_disabled"
        )

        await logger.log_user_message("test:123", "test", "123", "Test")
        await logger._flush_buffer()

        entries = await logger.query()
        assert len(entries) == 0

        await logger.close()


@pytest.mark.asyncio
async def test_tool_call_result_truncation(temp_logger):
    """Test that long tool results are truncated."""
    long_result = "x" * 2000  # Longer than 1000 char limit

    await temp_logger.log_tool_call(
        "test:123",
        "test_tool",
        "tool-1",
        {},
        long_result,
        ToolCallStatus.SUCCESS,
    )

    await temp_logger._flush_buffer()

    entries = await temp_logger.query(filters={"log_type": "tool_call"})
    assert len(entries) == 1
    assert len(entries[0]["result"]) <= 1015  # 1000 + "... (truncated)" (15 chars)
    assert "truncated" in entries[0]["result"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
