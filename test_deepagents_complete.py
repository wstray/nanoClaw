"""Complete test for DeepAgents integration."""
import asyncio
import sys
import os

# Add project to path
sys.path.insert(0, 'D:/projects/nanoClaw')

async def main():
    print("=" * 60)
    print("DeepAgents Integration Test")
    print("=" * 60)

    # Test 1: Config loading
    print("\n[1] Testing configuration loading...")
    try:
        from nanoclaw.core.config import get_config
        config = get_config()
        provider, api_key, model, base_url = config.get_active_provider()
        print(f"  [OK] Provider: {provider}")
        print(f"  [OK] Model: {model}")
        print(f"  [OK] API Key: {'*' * 20}{api_key[-4:]}")
        print(f"  [OK] DeepAgents enabled: {config.agent.deepagents.enabled}")
    except Exception as e:
        print(f"  [FAIL] Config loading failed: {e}")
        return

    # Test 2: Agent initialization
    print("\n[2] Testing agent initialization...")
    try:
        from nanoclaw.core.agent import get_agent
        agent = get_agent()
        print(f"  [OK] Agent created successfully")
        print(f"  [OK] Model: {agent.model}")
        print(f"  [OK] Provider: {agent.provider}")
    except Exception as e:
        print(f"  [FAIL] Agent init failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test 3: Simple message
    print("\n[3] Testing simple message...")
    try:
        response = await agent.run(
            "你好，请用一句话介绍你自己",
            session_id="test_session_simple"
        )
        print(f"  [OK] Response: {response[:100]}...")
    except Exception as e:
        print(f"  [FAIL] Simple message failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test 4: Complex task (planning)
    print("\n[4] Testing complex task (should trigger planning)...")
    try:
        response = await agent.run(
            "帮我研究一下 Python asyncio 的最佳实践，并总结 3 个关键点",
            session_id="test_session_complex"
        )
        print(f"  [OK] Response received")
        print(f"  [OK] Length: {len(response)} characters")
        # Check if planning keywords appear
        if "plan" in response.lower() or "步骤" in response or "首先" in response:
            print(f"  [OK] Appears to use planning!")
    except Exception as e:
        print(f"  [FAIL] Complex task failed: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("[SUCCESS] All tests passed!")
    print("=" * 60)
    print("\nYour DeepAgents integration is working correctly!")
    print("\nYou can now use:")
    print("  - uv run nanoclaw serve")
    print("  - Or: .venv\\Scripts\\python.exe -m nanoclaw.cli.main serve")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Test stopped by user")
    except Exception as e:
        print(f"\n\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
