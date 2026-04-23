"""Configuration management with pydantic validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from nanoclaw.core.jsonl_logger import JSONLLoggerConfig


class OpenRouterConfig(BaseModel):
    """OpenRouter API configuration."""

    api_key: str = Field(alias="apiKey")
    default_model: str = Field(
        default="anthropic/claude-sonnet-4", alias="defaultModel"
    )


class AnthropicConfig(BaseModel):
    """Anthropic API configuration."""

    api_key: str = Field(alias="apiKey")
    default_model: str = Field(
        default="claude-sonnet-4-20250514", alias="defaultModel"
    )


class OpenAIConfig(BaseModel):
    """OpenAI API configuration."""

    api_key: str = Field(alias="apiKey")
    default_model: str = Field(default="gpt-4o", alias="defaultModel")
    base_url: Optional[str] = Field(default=None, alias="baseUrl")


class DeepSeekConfig(BaseModel):
    """DeepSeek API configuration."""

    api_key: str = Field(alias="apiKey")
    default_model: str = Field(default="deepseek-chat", alias="defaultModel")
    base_url: Optional[str] = Field(default="https://api.deepseek.com", alias="baseUrl")


class ProvidersConfig(BaseModel):
    """LLM providers configuration."""

    openrouter: Optional[OpenRouterConfig] = None
    anthropic: Optional[AnthropicConfig] = None
    openai: Optional[OpenAIConfig] = None
    deepseek: Optional[DeepSeekConfig] = None

    model_config = {"populate_by_name": True}


class TelegramConfig(BaseModel):
    """Telegram bot configuration."""

    enabled: bool = False
    token: str = ""
    allow_from: list[str] = Field(default_factory=list, alias="allowFrom")

    model_config = {"populate_by_name": True}


class EteamsConfig(BaseModel):
    """Eteams IM configuration."""

    enabled: bool = False
    base_url: str = Field(default="", alias="baseUrl")
    phone: str = ""
    encrypted_password: str = Field(default="", alias="encryptedPassword")
    device_type: int = Field(default=9, alias="deviceType")
    allow_from: list[str] = Field(default_factory=list, alias="allowFrom")

    model_config = {"populate_by_name": True}


class ChannelsConfig(BaseModel):
    """Communication channels configuration."""

    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    eteams: EteamsConfig = Field(default_factory=EteamsConfig)


class WebSearchConfig(BaseModel):
    """Web search tool configuration."""

    api_key: str = Field(default="", alias="apiKey")
    provider: str = "brave"

    model_config = {"populate_by_name": True}


class ShellConfig(BaseModel):
    """Shell execution configuration."""

    enabled: bool = True
    timeout: int = 30
    confirm_dangerous: bool = Field(default=True, alias="confirmDangerous")
    inherit_env: bool = Field(default=False, alias="inheritEnv")
    env_vars: dict[str, str] = Field(default_factory=dict, alias="envVars")

    model_config = {"populate_by_name": True}


class RobocorpConfig(BaseModel):
    """Robocorp RPA configuration."""

    rcc_path: str = Field(default="", alias="rccPath")
    default_timeout: int = Field(default=300, alias="defaultTimeout")
    robots_file: str = Field(default="", alias="robotsFile")
    robots: dict[str, str] = Field(default_factory=dict)
    """Pre-registered robots: name -> path mapping.

    Example:
        "robots": {
            "invoice-bot": "/path/to/invoice-robot",
            "scraper": "C:/robots/web-scraper"
        }
    """

    model_config = {"populate_by_name": True}


class ToolsConfig(BaseModel):
    """Tools configuration."""

    shell: ShellConfig = Field(default_factory=ShellConfig)
    web_search: WebSearchConfig = Field(
        default_factory=WebSearchConfig, alias="webSearch"
    )
    robocorp: RobocorpConfig = Field(default_factory=RobocorpConfig)

    model_config = {"populate_by_name": True}


class MemoryConfig(BaseModel):
    """Memory system configuration."""

    max_history: int = Field(default=50, alias="maxHistory")
    semantic_search: bool = Field(default=False, alias="semanticSearch")

    model_config = {"populate_by_name": True}


class AgentDefaults(BaseModel):
    """Agent default settings."""

    model: str = ""  # Empty means use provider's defaultModel


class AgentsConfig(BaseModel):
    """Agents configuration."""

    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class DeepAgentsConfig(BaseModel):
    """LangChain DeepAgents configuration."""

    enabled: bool = Field(default=True)
    enable_planning: bool = Field(default=True, alias="enablePlanning")
    enable_subagents: bool = Field(default=True, alias="enableSubagents")
    tavily_api_key: str = Field(default="", alias="tavilyApiKey")

    model_config = {"populate_by_name": True}


class AgentConfig(BaseModel):
    """Agent runtime configuration."""

    max_iterations: int = Field(default=15, alias="maxIterations")
    max_tokens_per_session: int = Field(default=50000, alias="maxTokensPerSession")
    session_timeout: int = Field(default=300, alias="sessionTimeout")
    system_prompt: str = Field(default="", alias="systemPrompt")
    deepagents: DeepAgentsConfig = Field(default_factory=DeepAgentsConfig)

    model_config = {"populate_by_name": True}


class DashboardConfig(BaseModel):
    """Dashboard configuration."""

    enabled: bool = True
    port: int = 18790
    password: Optional[str] = None


class LangfuseConfig(BaseModel):
    """Langfuse observability configuration."""

    enabled: bool = False
    public_key: str = Field(default="", alias="publicKey")
    secret_key: str = Field(default="", alias="secretKey")
    host: str = Field(default="https://cloud.langfuse.com", alias="host")
    """Langfuse host URL. Use https://us.cloud.langfuse.com for US cloud,
    or your self-hosted URL."""
    release: Optional[str] = None
    """Optional release/version tag for tracking deployments."""
    environment: Optional[str] = Field(default=None, alias="environment")
    """Optional environment (e.g., 'production', 'staging', 'development')."""

    model_config = {"populate_by_name": True}


class Config(BaseModel):
    """Main configuration model."""

    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    jsonl_logging: JSONLLoggerConfig = Field(default_factory=JSONLLoggerConfig)
    langfuse: LangfuseConfig = Field(default_factory=LangfuseConfig)

    model_config = {"populate_by_name": True}

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> Config:
        """Load configuration from file."""
        if config_path is None:
            config_path = Path.home() / ".nanoclaw" / "config.json"

        if not config_path.exists():
            raise FileNotFoundError(
                f"Config not found at {config_path}. Run 'nanoclaw init' first."
            )

        data = json.loads(config_path.read_text())
        return cls(**data)

    def get_active_provider(self) -> tuple[str, str, str, Optional[str]]:
        """
        Get active provider details.

        Returns: (provider_name, api_key, default_model, base_url)
        """
        if self.providers.deepseek:
            # DeepSeek uses OpenAI-compatible API
            return (
                "openai",  # Use openai client code
                self.providers.deepseek.api_key,
                self.providers.deepseek.default_model,
                self.providers.deepseek.base_url,  # Use configured base_url
            )
        elif self.providers.openrouter:
            return (
                "openrouter",
                self.providers.openrouter.api_key,
                self.providers.openrouter.default_model,
                None,
            )
        elif self.providers.anthropic:
            return (
                "anthropic",
                self.providers.anthropic.api_key,
                self.providers.anthropic.default_model,
                None,
            )
        elif self.providers.openai:
            return (
                "openai",
                self.providers.openai.api_key,
                self.providers.openai.default_model,
                self.providers.openai.base_url,
            )
        else:
            raise ValueError("No LLM provider configured.")

    def get_default_model(self) -> str:
        """Get the default model from agents config or provider."""
        if self.agents.defaults.model:
            return self.agents.defaults.model
        _, _, model, _ = self.get_active_provider()
        return model


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global config instance."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def set_config(config: Config) -> None:
    """Set the global config instance."""
    global _config
    _config = config


def get_workspace_path() -> Path:
    """Get the workspace directory path."""
    return Path.home() / ".nanoclaw" / "workspace"


def get_data_path() -> Path:
    """Get the data directory path."""
    data_dir = Path.home() / ".nanoclaw" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_logs_path() -> Path:
    """Get the logs directory path."""
    from nanoclaw.core.config import get_config

    config = get_config()
    if config.jsonl_logging.log_dir:
        log_dir = Path(config.jsonl_logging.log_dir)
    else:
        log_dir = Path.home() / ".nanoclaw" / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir
