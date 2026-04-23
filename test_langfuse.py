#!/usr/bin/env python3
"""Test script to verify Langfuse integration."""

import asyncio
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nanoclaw.core.config import get_config


async def test_langfuse_config():
    """Test Langfuse configuration loading."""
    print("=" * 60)
    print("Testing Langfuse Configuration")
    print("=" * 60)

    try:
        config = get_config()
        print(f"\nLangfuse enabled: {config.langfuse.enabled}")
        print(f"Langfuse public_key set: {bool(config.langfuse.public_key)}")
        print(f"Langfuse secret_key set: {bool(config.langfuse.secret_key)}")
        print(f"Langfuse host: {config.langfuse.host}")
        print(f"Langfuse release: {config.langfuse.release}")
        print(f"Langfuse environment: {config.langfuse.environment}")
    except Exception as e:
        print(f"Error loading config: {e}")
        return False

    return True


async def test_langfuse_callback():
    """Test Langfuse callback initialization."""
    print("\n" + "=" * 60)
    print("Testing Langfuse Callback Initialization")
    print("=" * 60)

    try:
        from langfuse.langchain import CallbackHandler
        print("✓ Successfully imported CallbackHandler")
    except ImportError as e:
        print(f"✗ Failed to import CallbackHandler: {e}")
        return False

    config = get_config()

    if not config.langfuse.enabled:
        print("⚠ Langfuse is disabled in config")
        return False

    if not config.langfuse.public_key or not config.langfuse.secret_key:
        print("⚠ Langfuse credentials not configured")
        return False

    try:
        callback = CallbackHandler(
            public_key=config.langfuse.public_key,
            secret_key=config.langfuse.secret_key,
            host=config.langfuse.host,
            release=config.langfuse.release,
            environment=config.langfuse.environment,
        )
        print("✓ Successfully created CallbackHandler")

        # Check if handler has langfuse attribute for flush
        if hasattr(callback, 'langfuse'):
            print("✓ Callback has langfuse attribute")
        if hasattr(callback, 'flush'):
            print("✓ Callback has flush method")

        # Test flush
        try:
            if hasattr(callback, 'langfuse') and hasattr(callback.langfuse, 'flush'):
                callback.langfuse.flush()
                print("✓ Successfully flushed Langfuse data")
            elif hasattr(callback, 'flush'):
                callback.flush()
                print("✓ Successfully flushed callback")
        except Exception as e:
            print(f"⚠ Flush test warning (may be expected if no data): {e}")

        return True
    except Exception as e:
        print(f"✗ Failed to create CallbackHandler: {e}")
        return False


async def test_agent_with_langfuse():
    """Test agent initialization with Langfuse."""
    print("\n" + "=" * 60)
    print("Testing Agent Initialization with Langfuse")
    print("=" * 60)

    try:
        from nanoclaw.core.agent import get_agent
        print("✓ Successfully imported get_agent")

        agent = get_agent()
        print("✓ Successfully created agent")

        # Check if agent has langfuse_callback
        if agent.langfuse_callback:
            print("✓ Agent has langfuse_callback")
        else:
            print("⚠ Agent does not have langfuse_callback (may be disabled)")

        # Check if agent has flush method
        if hasattr(agent, 'flush'):
            print("✓ Agent has flush method")

        return True
    except Exception as e:
        print(f"✗ Failed to create agent: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_manual_trace():
    """Test creating a manual trace with Langfuse."""
    print("\n" + "=" * 60)
    print("Testing Manual Langfuse Trace")
    print("=" * 60)

    config = get_config()

    if not config.langfuse.enabled:
        print("⚠ Langfuse is disabled, skipping manual trace test")
        return True

    try:
        from langfuse import Langfuse

        langfuse = Langfuse(
            public_key=config.langfuse.public_key,
            secret_key=config.langfuse.secret_key,
            host=config.langfuse.host,
        )
        print("✓ Successfully created Langfuse client")

        # Create a simple trace
        trace = langfuse.trace(
            name="test-trace",
            user_id="test-user",
            metadata={"test": True}
        )
        print(f"✓ Created trace with ID: {trace.id}")

        # Create a generation within the trace
        generation = trace.generation(
            name="test-generation",
            model="test-model",
            input={"message": "Hello"},
            output={"response": "World"},
        )
        print(f"✓ Created generation with ID: {generation.id}")

        # Flush to send data
        langfuse.flush()
        print("✓ Flushed data to Langfuse")

        print("\n✓ Manual trace test passed! Check your Langfuse dashboard.")
        return True
    except Exception as e:
        print(f"✗ Failed to create manual trace: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "Langfuse Integration Test" + " " * 18 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    results = []

    results.append(("Config Loading", await test_langfuse_config()))
    results.append(("Callback Initialization", await test_langfuse_callback()))
    results.append(("Agent with Langfuse", await test_agent_with_langfuse()))
    results.append(("Manual Trace", await test_manual_trace()))

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    all_passed = all(r[1] for r in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("All tests passed!")
        print("\nNext steps:")
        print("1. Run 'nanoclaw chat' and send a message")
        print("2. Check your Langfuse dashboard for traces")
        print("3. If no traces appear, check LANGFUSE_HOST and credentials")
    else:
        print("Some tests failed. Please check the errors above.")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
