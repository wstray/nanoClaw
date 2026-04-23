"""Test JSONL logger functionality."""

import asyncio
import json
from pathlib import Path

from nanoclaw.core.config import get_config, get_logs_path
from nanoclaw.core.jsonl_logger import JSONLLogger, set_jsonl_logger, LogLevel


async def test_jsonl_logging():
    """Test that JSONL logging works correctly."""
    print("=== JSONL Logger Test ===")

    # Get config
    config = get_config()
    print(f"JSONL logging enabled: {config.jsonl_logging.enabled}")

    if not config.jsonl_logging.enabled:
        print("ERROR: JSONL logging is disabled in config!")
        return

    # Get logs path
    logs_path = get_logs_path()
    print(f"Logs directory: {logs_path}")

    # Check existing files
    log_files = list(logs_path.glob("*.jsonl*"))
    print(f"Existing log files: {len(log_files)}")
    for f in log_files:
        size = f.stat().st_size
        print(f"  - {f.name} ({size} bytes)")

    # Create logger
    logger = JSONLLogger(
        log_dir=logs_path,
        config=config.jsonl_logging,
        log_name="nanoclaw"
    )
    set_jsonl_logger(logger)

    print("\n=== Writing test logs ===")

    # Test different log types
    await logger.log_user_message(
        session_id="test:123",
        channel_id="test_channel",
        user_id="test_user",
        content="Hello, this is a test message!"
    )
    print("[OK] User message logged")

    await logger.log_agent_thinking(
        session_id="test:123",
        iteration=1,
        thought_type="reasoning",
        content="Test thinking process"
    )
    print("[OK] Agent thinking logged")

    await logger.log_agent_response(
        session_id="test:123",
        content="Test agent response",
        tokens_used=50,
        iterations=1,
        tool_calls_count=0,
        duration_ms=100
    )
    print("[OK] Agent response logged")

    await logger.log_tool_call(
        session_id="test:123",
        tool_name="test_tool",
        tool_id="tool-123",
        parameters={"param1": "value1"},
        result="Test result",
        status="success",
        duration_ms=50
    )
    print("[OK] Tool call logged")

    await logger.log_system(
        level=LogLevel.INFO,
        component="test",
        message="Test system log"
    )
    print("[OK] System log logged")

    # Flush buffer to ensure data is written
    await logger._flush_buffer()
    print("\n[OK] Buffer flushed")

    # Check file size again
    log_files = list(logs_path.glob("*.jsonl"))
    print(f"\n=== After test ===")
    for f in log_files:
        size = f.stat().st_size
        print(f"  - {f.name} ({size} bytes)")

        # Read and display first few lines
        if size > 0:
            print(f"    Content preview:")
            with open(f, 'r', encoding='utf-8') as file:
                for i, line in enumerate(file):
                    if i >= 3:  # Show first 3 lines
                        break
                    entry = json.loads(line)
                    print(f"      [{i+1}] {entry['log_type']}: {entry.get('content', entry.get('message', 'N/A'))[:60]}...")

    # Query logs
    print("\n=== Querying logs ===")
    all_entries = await logger.query(limit=10)
    print(f"Total entries found: {len(all_entries)}")
    for entry in all_entries:
        print(f"  - {entry['log_type']}: {entry.get('timestamp', 'N/A')}")

    # Get session history
    print("\n=== Session history ===")
    history = await logger.get_session_history("test:123")
    print(f"Session 'test:123' entries: {len(history)}")

    await logger.close()
    print("\n=== Test completed successfully ===")


if __name__ == "__main__":
    asyncio.run(test_jsonl_logging())
