"""Multi-provider LLM client with connection pooling."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

import aiohttp

from nanoclaw.core.logger import get_logger

logger = get_logger(__name__)


class LLMError(Exception):
    """LLM API error."""

    pass


@dataclass
class TokenUsage:
    """Token usage information."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.prompt_tokens + self.completion_tokens


@dataclass
class ToolCall:
    """Represents a tool call from the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Unified LLM response format."""

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)

    def to_message(self) -> dict[str, Any]:
        """Convert response to message format for context."""
        msg: dict[str, Any] = {"role": "assistant"}

        if self.content:
            msg["content"] = self.content

        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in self.tool_calls
            ]
            if "content" not in msg:
                msg["content"] = ""

        return msg


class ConnectionPool:
    """Shared HTTP session for the entire application."""

    _session: Optional[aiohttp.ClientSession] = None

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        """Get or create the shared session."""
        if cls._session is None or cls._session.closed:
            connector = aiohttp.TCPConnector(
                limit=20,
                limit_per_host=5,
                ttl_dns_cache=300,
                keepalive_timeout=30,
            )
            cls._session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return cls._session

    @classmethod
    async def close(cls) -> None:
        """Close the shared session."""
        if cls._session and not cls._session.closed:
            await cls._session.close()
            cls._session = None


class LLMClient:
    """
    Multi-provider LLM client.

    Supports OpenRouter, Anthropic, and OpenAI APIs.
    Uses shared connection pool for efficiency.
    """

    BASE_URLS = {
        "openrouter": "https://openrouter.ai/api/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "openai": "https://api.openai.com/v1",
    }

    def __init__(
        self,
        provider: str,
        api_key: str,
        default_model: str,
        base_url: Optional[str] = None,
    ):
        """
        Initialize LLM client.

        Args:
            provider: Provider name (openrouter, anthropic, openai)
            api_key: API key
            default_model: Default model to use
            base_url: Custom base URL (for proxies/local models)
        """
        self.provider = provider
        self.api_key = api_key
        self.model = default_model
        self.base_url = base_url or self.BASE_URLS.get(provider, "")

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """
        Send chat completion request.

        Args:
            messages: List of messages in OpenAI format
            tools: Optional list of tool schemas
            model: Optional model override

        Returns:
            LLMResponse with content and/or tool calls
        """
        model = model or self.model

        headers = self._build_headers()
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        # OpenAI GPT-5+ uses max_completion_tokens, others use max_tokens
        if self.provider == "openai" and model.startswith("gpt-5"):
            payload["max_completion_tokens"] = 4096
        else:
            payload["max_tokens"] = 4096

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        session = await ConnectionPool.get_session()

        if self.provider == "anthropic":
            endpoint = f"{self.base_url}/messages"
            payload = self._adapt_for_anthropic(payload)
        else:
            endpoint = f"{self.base_url}/chat/completions"

        try:
            async with session.post(
                endpoint, json=payload, headers=headers
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise LLMError(f"LLM API error {resp.status}: {error}")
                data = await resp.json()
        except aiohttp.ClientError as e:
            raise LLMError(f"Network error: {e}")

        return self._parse_response(data)

    def _build_headers(self) -> dict[str, str]:
        """Build request headers based on provider."""
        if self.provider == "anthropic":
            return {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
                "Accept-Encoding": "gzip, deflate",
            }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip, deflate",
        }
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/nanoclaw/nanoclaw"
            headers["X-Title"] = "nanoClaw"
        return headers

    def _adapt_for_anthropic(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Convert OpenAI format to Anthropic Messages API format."""
        messages = payload.get("messages", [])

        system_text = ""
        converted_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            elif msg["role"] == "tool":
                converted_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.get("tool_call_id", ""),
                                "content": msg["content"],
                            }
                        ],
                    }
                )
            elif msg["role"] == "assistant" and "tool_calls" in msg:
                content_blocks = []
                if msg.get("content"):
                    content_blocks.append({"type": "text", "text": msg["content"]})
                for tc in msg["tool_calls"]:
                    args = tc["function"]["arguments"]
                    if isinstance(args, str):
                        args = json.loads(args)
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["function"]["name"],
                            "input": args,
                        }
                    )
                converted_messages.append(
                    {"role": "assistant", "content": content_blocks}
                )
            else:
                converted_messages.append(msg)

        anthropic_payload: dict[str, Any] = {
            "model": payload["model"],
            "max_tokens": payload.get("max_tokens", 4096),
            "messages": converted_messages,
        }

        if system_text:
            anthropic_payload["system"] = system_text

        if "tools" in payload:
            anthropic_tools = []
            for tool in payload["tools"]:
                func = tool.get("function", tool)
                anthropic_tools.append(
                    {
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {}),
                    }
                )
            anthropic_payload["tools"] = anthropic_tools

        return anthropic_payload

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse response from any provider into unified format."""
        if self.provider == "anthropic":
            return self._parse_anthropic_response(data)
        return self._parse_openai_response(data)

    def _parse_anthropic_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse Anthropic Messages API response."""
        content = ""
        tool_calls = []

        for block in data.get("content", []):
            if block["type"] == "text":
                content += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block["id"],
                        name=block["name"],
                        arguments=block["input"],
                    )
                )

        usage_data = data.get("usage", {})
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=TokenUsage(
                prompt_tokens=usage_data.get("input_tokens", 0),
                completion_tokens=usage_data.get("output_tokens", 0),
            ),
        )

    def _parse_openai_response(self, data: dict[str, Any]) -> LLMResponse:
        """Parse OpenAI/OpenRouter chat completions response."""
        choice = data["choices"][0]
        message = choice["message"]

        tool_calls = []
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                args = tc["function"]["arguments"]
                if isinstance(args, str):
                    args = json.loads(args)
                tool_calls.append(
                    ToolCall(
                        id=tc["id"],
                        name=tc["function"]["name"],
                        arguments=args,
                    )
                )

        usage_data = data.get("usage", {})
        return LLMResponse(
            content=message.get("content", "") or "",
            tool_calls=tool_calls,
            usage=TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
            ),
        )

    async def test_connection(self) -> bool:
        """Test if the API connection works."""
        try:
            response = await self.chat(
                messages=[{"role": "user", "content": "hi"}],
                model=self.model,
            )
            return bool(response.content or response.tool_calls)
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False


# Global LLM client instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get the global LLM client instance."""
    global _llm_client
    if _llm_client is None:
        from nanoclaw.core.config import get_config

        config = get_config()
        provider, api_key, model, base_url = config.get_active_provider()
        # Use model from agents.defaults if set
        model = config.get_default_model()
        _llm_client = LLMClient(provider, api_key, model, base_url)
    return _llm_client


def set_llm_client(client: LLMClient) -> None:
    """Set the global LLM client instance."""
    global _llm_client
    _llm_client = client
