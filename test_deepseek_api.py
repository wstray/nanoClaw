"""Test DeepSeek API directly to find correct endpoint."""
import asyncio
import os

# Set API key and base URL from config
os.environ["OPENAI_API_KEY"] = "sk-598b2d4c48a246929d38926bb4ed0694"
os.environ["OPENAI_BASE_URL"] = "https://api.deepseek.com"

from langchain_openai import ChatOpenAI

async def test_deepseek():
    print("Testing DeepSeek API connection...")
    print(f"Base URL: {os.environ.get('OPENAI_BASE_URL')}")

    # Test 1: Default configuration
    print("\n[Test 1] Default ChatOpenAI configuration")
    try:
        llm = ChatOpenAI(
            model="deepseek-chat",
            temperature=0.7
        )
        result = await llm.ainvoke("Hello, say hi in one word")
        print(f"Success! Response: {result.content}")
    except Exception as e:
        print(f"Failed: {e}")

    # Test 2: With explicit base_url
    print("\n[Test 2] With explicit base_url parameter")
    try:
        llm = ChatOpenAI(
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
            temperature=0.7
        )
        result = await llm.ainvoke("Hello, say hi in one word")
        print(f"Success! Response: {result.content}")
    except Exception as e:
        print(f"Failed: {e}")

    # Test 3: Try /v1 path
    print("\n[Test 3] With /v1 in base_url")
    try:
        llm = ChatOpenAI(
            model="deepseek-chat",
            base_url="https://api.deepseek.com/v1",
            temperature=0.7
        )
        result = await llm.ainvoke("Hello, say hi in one word")
        print(f"Success! Response: {result.content}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_deepseek())
