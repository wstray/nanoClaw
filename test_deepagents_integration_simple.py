"""Simple test for DeepAgents integration without nanoclaw command."""
import asyncio
import sys
sys.path.insert(0, 'D:/projects/nanoClaw')

async def test_agent():
    from nanoclaw.core.agent import get_agent

    print("Getting agent...")
    agent = get_agent()

    print("Testing simple message...")
    response = await agent.run(
        "你好，请用一句话介绍你自己",
        session_id="test_session_123"
    )

    print(f"\n=== Agent Response ===")
    print(response)
    print(f"=== End ===\n")

    return response

if __name__ == "__main__":
    try:
        result = asyncio.run(test_agent())
        print("\n[SUCCESS] Test completed!")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
