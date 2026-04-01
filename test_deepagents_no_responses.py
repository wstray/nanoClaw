"""Test DeepAgents with DeepSeek WITHOUT Responses API."""
import asyncio
import os
import sys
sys.path.insert(0, 'D:/projects/nanoClaw')

# Set environment variables
os.environ["OPENAI_API_KEY"] = "sk-598b2d4c48a246929d38926bb4ed0694"
os.environ["OPENAI_BASE_URL"] = "https://api.deepseek.com"

async def test():
    from deepagents import create_deep_agent
    from langchain.chat_models import init_chat_model

    print("Initializing model WITHOUT Responses API...")
    model = init_chat_model(
        "openai:deepseek-chat",
        use_responses_api=False,  # Disable Responses API
    )

    print("\nCreating DeepAgents...")
    agent = create_deep_agent(
        model=model,  # Use pre-initialized model
        tools=[],
        system_prompt="You are a helpful assistant. Respond very briefly.",
    )

    print("Invoking DeepAgents...")
    try:
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": "Say hello in one word"}]
        })

        print("\n=== SUCCESS ===")
        if isinstance(result, dict) and "messages" in result:
            messages = result["messages"]
            if messages:
                last_msg = messages[-1]
                if hasattr(last_msg, 'content'):
                    print(f"Response: {last_msg.content}")

    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(test())
