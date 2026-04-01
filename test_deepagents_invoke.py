import asyncio
from deepagents import create_deep_agent

async def test_invoke():
    # Create agent
    agent = create_deep_agent(model="anthropic:claude-sonnet-4-6")

    # Test invoke
    print("Testing ainvoke...")
    try:
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": "Say hello"}]
        })
        print("\nResult type:", type(result))
        print("\nResult keys:", result.keys() if isinstance(result, dict) else "Not a dict")
        print("\nResult:", result)
    except Exception as e:
        print("Error:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_invoke())
