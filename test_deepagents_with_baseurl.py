"""Test DeepAgents with DeepSeek base URL."""
import asyncio
import os
import sys
sys.path.insert(0, 'D:/projects/nanoClaw')

# Set environment variables
os.environ["OPENAI_API_KEY"] = "sk-598b2d4c48a246929d38926bb4ed0694"
os.environ["OPENAI_BASE_URL"] = "https://api.deepseek.com"

async def test():
    from deepagents import create_deep_agent

    print("Creating DeepAgents with DeepSeek...")
    print(f"Base URL: {os.environ.get('OPENAI_BASE_URL')}\n")

    # Create agent with DeepSeek
    agent = create_deep_agent(
        model="openai:deepseek-chat",
        tools=[],  # No tools for this test
        system_prompt="You are a helpful assistant. Respond very briefly.",
    )

    print("Invoking DeepAgents...")
    try:
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": "Say hello in one word"}]
        })

        print("\n=== Result ===")
        print(f"Type: {type(result)}")
        print(f"Keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")

        if isinstance(result, dict) and "messages" in result:
            messages = result["messages"]
            print(f"\nNumber of messages: {len(messages)}")
            if messages:
                last_msg = messages[-1]
                print(f"Last message type: {type(last_msg)}")
                if hasattr(last_msg, 'content'):
                    print(f"Response: {last_msg.content}")

        print("\n[SUCCESS] DeepAgents with DeepSeek works!")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
